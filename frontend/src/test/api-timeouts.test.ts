import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { createApiClient } from '../lib/api/client'

const api = createApiClient('/api/v1')
const schema = z.object({ ok: z.literal(true) })
const success = () => Response.json({ ok: true })
const timeoutError = {
  name: 'ApiError',
  kind: 'timeout',
  status: undefined,
  message: 'The request took too long.',
}

describe('API request deadline', () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] }))
  afterEach(() => vi.useRealTimers())

  it('uses the 12-second default when no override is provided', async () => {
    const headers = Promise.withResolvers<Response>()
    const transport = vi.spyOn(globalThis, 'fetch').mockReturnValue(headers.promise)
    const result = api.request({ path: '/me', schema }, 'test-access')
    const assertion = expect(result).rejects.toMatchObject(timeoutError)
    const signal = transport.mock.calls[0]?.[1]?.signal
    await vi.advanceTimersByTimeAsync(11_999)
    expect(signal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    await assertion
    expect(signal?.aborted).toBe(true)
    headers.resolve(success())
  })

  it('allows a long response to succeed within a 90-second override', async () => {
    const headers = Promise.withResolvers<Response>()
    const transport = vi.spyOn(globalThis, 'fetch').mockReturnValue(headers.promise)
    const result = api.request({ path: '/rag/ask', method: 'POST', schema, timeoutMs: 90_000 }, 'test-access')
    const signal = transport.mock.calls[0]?.[1]?.signal
    await vi.advanceTimersByTimeAsync(36_300)
    expect(signal?.aborted).toBe(false)
    headers.resolve(success())
    await expect(result).resolves.toEqual({ ok: true })
    await vi.advanceTimersByTimeAsync(90_000)
    expect(signal?.aborted).toBe(false)
  })

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, 300_001])(
    'rejects invalid timeout %s before starting any request',
    async (timeoutMs) => {
      const transport = vi.spyOn(globalThis, 'fetch')
      await expect(api.request({ path: '/me', schema, timeoutMs }, 'test-access'))
        .rejects.toThrow('Invalid API request timeout.')
      expect(transport).not.toHaveBeenCalled()
    },
  )

  it('honors a short override and keeps the timeout when a caller cancels later', async () => {
    const headers = Promise.withResolvers<Response>()
    const transport = vi.spyOn(globalThis, 'fetch').mockReturnValue(headers.promise)
    const caller = new AbortController()
    const result = api.request({ path: '/me', schema, signal: caller.signal, timeoutMs: 75 }, 'test-access')
    const assertion = expect(result).rejects.toMatchObject(timeoutError)
    const signal = transport.mock.calls[0]?.[1]?.signal
    await vi.advanceTimersByTimeAsync(74)
    expect(signal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    caller.abort()
    await assertion
    headers.reject(new Error('private transport detail after timeout'))
    await vi.advanceTimersByTimeAsync(0)
  })

  it('preserves cancellation before any request is sent', async () => {
    const caller = new AbortController()
    caller.abort()
    const transport = vi.spyOn(globalThis, 'fetch')
    await expect(api.request({ path: '/me', schema, signal: caller.signal }, 'test-access'))
      .rejects.toBe(caller.signal.reason)
    expect(transport).not.toHaveBeenCalled()
  })

  it('keeps explicit cancellation when the body arrives late', async () => {
    const body = Promise.withResolvers<unknown>()
    const response = success()
    const read = vi.spyOn(response, 'json').mockReturnValue(body.promise)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
    const caller = new AbortController()
    const result = api.request({ path: '/me', schema, signal: caller.signal }, 'test-access')
    await vi.advanceTimersByTimeAsync(0)
    expect(read).toHaveBeenCalledOnce()
    caller.abort()
    await expect(result).rejects.toBe(caller.signal.reason)
    body.resolve({ ok: true })
    await vi.advanceTimersByTimeAsync(0)
  })

  it('shares one deadline between response headers and body processing', async () => {
    const headers = Promise.withResolvers<Response>()
    const body = Promise.withResolvers<unknown>()
    const response = success()
    const read = vi.spyOn(response, 'json').mockReturnValue(body.promise)
    vi.spyOn(globalThis, 'fetch').mockReturnValue(headers.promise)
    const result = api.request({ path: '/me', schema, timeoutMs: 100 }, 'test-access')
    const assertion = expect(result).rejects.toMatchObject(timeoutError)
    await vi.advanceTimersByTimeAsync(80)
    headers.resolve(response)
    await vi.advanceTimersByTimeAsync(0)
    expect(read).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(20)
    await assertion
    body.reject(new Error('private body diagnostic after timeout'))
    await vi.advanceTimersByTimeAsync(0)
  })

  it('detects an elapsed deadline even if synchronous validation delayed the timer', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(success())
    const clock = vi.spyOn(performance, 'now').mockReturnValue(0)
    const slowSchema = schema.transform((value) => {
      clock.mockReturnValue(101)
      return value
    })
    await expect(api.request({ path: '/me', schema: slowSchema, timeoutMs: 100 }, 'test-access'))
      .rejects.toMatchObject(timeoutError)
  })

  it.each([
    ['/rag/search', 30_000],
    ['/rag/ask', 90_000],
    ['/rag/secure-ask', 90_000],
    ['/documents/00000000-0000-4000-8000-000000000014/index', 120_000],
  ] as const)('does not replay a timed-out POST to %s', async (path, timeoutMs) => {
    const headers = Promise.withResolvers<Response>()
    const transport = vi.spyOn(globalThis, 'fetch').mockReturnValue(headers.promise)
    const result = api.request({ path, method: 'POST', schema, timeoutMs }, 'test-access')
    const assertion = expect(result).rejects.toMatchObject(timeoutError)
    await vi.advanceTimersByTimeAsync(timeoutMs)
    await assertion
    headers.resolve(new Response(null, { status: 503 }))
    await vi.advanceTimersByTimeAsync(timeoutMs)
    expect(transport).toHaveBeenCalledOnce()
  })

  it.each([
    ['/rag/secure-ask', 90_000],
    ['/documents/00000000-0000-4000-8000-000000000014/index', 120_000],
  ] as const)('does not replay a POST to %s when the backend reports 503', async (path, timeoutMs) => {
    const response = Response.json({ detail: 'private upstream diagnostic' }, { status: 503 })
    const read = vi.spyOn(response, 'json')
    const transport = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
    await expect(api.request({ path, method: 'POST', schema, timeoutMs }, 'test-access'))
      .rejects.toMatchObject({ kind: 'http', status: 503, message: 'The service is temporarily unavailable.' })
    await vi.advanceTimersByTimeAsync(timeoutMs)
    expect(read).not.toHaveBeenCalled()
    expect(transport).toHaveBeenCalledOnce()
  })
})
