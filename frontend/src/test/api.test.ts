import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { ApiError, createApiClient } from '../lib/api/client'
import { readEnvironment } from '../lib/config/environment'
import { backend, server } from './server'

const schema = z.object({ ok: z.literal(true) })
const api = createApiClient('/api/v1')

describe('same-origin typed API', () => {
  it('validates data and sends the current Bearer without a role header', async () => {
    const fetchOptions = vi.spyOn(globalThis, 'fetch')
    const receive = vi.fn()
    server.use(http.get(`${backend}/me`, ({ request }) => {
      receive(request.headers.get('authorization'), request.headers.get('x-role'))
      return HttpResponse.json({ ok: true, extra: 'discarded' })
    }))
    await expect(api.request({ path: '/me', schema }, 'test-access')).resolves.toEqual({ ok: true })
    expect(receive).toHaveBeenCalledExactlyOnceWith('Bearer test-access', null)
    expect(fetchOptions).toHaveBeenCalledExactlyOnceWith(
      new URL(`${backend}/me`),
      expect.objectContaining({ redirect: 'error', credentials: 'omit', cache: 'no-store' }),
    )
  })

  it.each([
    [400, 'Check the information you entered.'],
    [401, 'Your session could not be verified.'],
    [403, 'You do not have access to this resource.'],
    [404, 'This resource is unavailable.'],
    [409, 'The request conflicts with a recent change.'],
    [413, 'The file is too large.'],
    [415, 'This file type is not supported.'],
    [422, 'Check the information you entered.'],
    [503, 'The service is temporarily unavailable.'],
  ])('maps HTTP %s without exposing backend details or retrying a POST', async (status, message) => {
    const calls = vi.fn()
    server.use(http.post(`${backend}/rag/ask`, async ({ request }) => {
      calls(await request.json())
      return HttpResponse.json({ detail: 'private upstream token test-access' }, { status })
    }))
    const body = { question: 'What material is available?' }
    await expect(api.request({ path: '/rag/ask', method: 'POST', body, schema }, 'test-access'))
      .rejects.toMatchObject({ kind: 'http', status, message })
    expect(calls).toHaveBeenCalledExactlyOnceWith(body)
  })

  it('classifies a network failure', async () => {
    server.use(http.get(`${backend}/me`, () => HttpResponse.error()))
    await expect(api.request({ path: '/me', schema }, 'test-access'))
      .rejects.toMatchObject({ name: 'ApiError', kind: 'network' })
  })

  it('rejects invalid JSON', async () => {
    server.use(http.get(`${backend}/me`, () => HttpResponse.text('private upstream text')))
    await expect(api.request({ path: '/me', schema }, 'test-access'))
      .rejects.toMatchObject({ kind: 'invalid-response', message: 'The service returned an unexpected response.' })
  })

  it('cancels an active request', async () => {
    const called = Promise.withResolvers<void>()
    const reply = Promise.withResolvers<void>()
    server.use(http.get(`${backend}/me`, async () => {
      called.resolve()
      await reply.promise
      return HttpResponse.json({ ok: true })
    }))
    const controller = new AbortController()
    const response = api.request({ path: '/me', schema, signal: controller.signal }, 'test-access')
    const assertion = expect(response).rejects.toMatchObject({ name: 'AbortError' })
    await called.promise
    controller.abort()
    reply.resolve()
    await assertion
  })

  it('rejects absolute and protocol-relative API URLs', async () => {
    expect(() => createApiClient('//other.example/api')).toThrow(TypeError)
    await expect(api.request({ path: '//other.example/me', schema }, 'test-access')).rejects.toThrow(TypeError)
    await expect(api.request({ path: '/..//other.example/me', schema }, 'test-access')).rejects.not.toBeInstanceOf(ApiError)
  })
})

describe('public environment', () => {
  const values = { supabaseUrl: 'https://project.example.test', publishableKey: 'sb_publishable_synthetic', apiBase: '' }
  it('accepts a valid publishable key and defaults to the FastAPI prefix', () => {
    expect(readEnvironment(values)).toEqual({ ...values, apiBase: '/api/v1' })
  })
  it.each([
    { publishableKey: '' },
    { publishableKey: 'sb_secret_test_rejected' },
    { publishableKey: 'eyJ_legacy_key_rejected' },
    { supabaseUrl: 'https://name:password@project.example.test' },
    { supabaseUrl: 'http://project.example.test' },
    { apiBase: 'https://api.example.test/v1' },
  ])('fails closed for invalid config %j', (patch) => {
    expect(readEnvironment({ ...values, ...patch })).toBeNull()
  })
})
