import type { ZodType } from 'zod'
import { isApiPath } from '../config/environment'
import { DEFAULT_API_TIMEOUT_MS, MAX_API_TIMEOUT_MS } from '../config/timeouts'

const statusMessages: Partial<Record<number, string>> = {
  400: 'Check the information you entered.',
  401: 'Your session could not be verified.',
  403: 'You do not have access to this resource.',
  404: 'This resource is unavailable.',
  409: 'The request conflicts with a recent change.',
  413: 'The file is too large.',
  415: 'This file type is not supported.',
  422: 'Check the information you entered.',
  503: 'The service is temporarily unavailable.',
}

const requestMessages = {
  network: 'Could not reach the service. Check your connection and try again.',
  timeout: 'The request took too long.',
  'invalid-response': 'The service returned an unexpected response.',
}

export class ApiError extends Error {
  constructor(
    readonly kind: 'http' | keyof typeof requestMessages,
    readonly status?: number,
  ) {
    super(
      kind === 'http'
        ? statusMessages[status ?? 0] ?? 'The service could not complete this request.'
        : requestMessages[kind],
    )
    this.name = 'ApiError'
  }
}

export interface ApiRequest<T> {
  path: string
  schema: ZodType<T>
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
}

async function runWithDeadline<T>(
  timeoutMs: number,
  cancellation: AbortSignal | undefined,
  run: (signal: AbortSignal, checkDeadline: () => void) => Promise<T>,
): Promise<T> {
  cancellation?.throwIfAborted()
  const timeout = new AbortController()
  const signal = cancellation ? AbortSignal.any([cancellation, timeout.signal]) : timeout.signal
  const expiresAt = performance.now() + timeoutMs
  const expire = () => timeout.abort(new ApiError('timeout'))
  const timer = setTimeout(expire, timeoutMs)
  let onAbort: (() => void) | undefined

  function checkDeadline() {
    signal.throwIfAborted()
    // A timer cannot run during synchronous JSON/schema work.
    if (performance.now() >= expiresAt) {
      expire()
      signal.throwIfAborted()
    }
  }

  try {
    const aborted = new Promise<never>((_, reject) => {
      onAbort = () => reject(signal.reason)
      signal.addEventListener('abort', onAbort, { once: true })
    })
    // Settle even if a body reader ignores abort. Promise.race also observes late rejections.
    const result = await Promise.race([aborted, run(signal, checkDeadline)])
    checkDeadline()
    return result
  } finally {
    clearTimeout(timer)
    if (onAbort) signal.removeEventListener('abort', onAbort)
  }
}

export function createApiClient(base: string) {
  if (!isApiPath(base)) throw new TypeError('Invalid API base.')

  return {
    async request<T>(request: ApiRequest<T>, token: string): Promise<T> {
      if (!isApiPath(request.path)) throw new TypeError('Invalid API path.')
      const timeoutMs = request.timeoutMs === undefined ? DEFAULT_API_TIMEOUT_MS : request.timeoutMs
      if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > MAX_API_TIMEOUT_MS) {
        throw new RangeError('Invalid API request timeout.')
      }

      return runWithDeadline(timeoutMs, request.signal, async (signal, checkDeadline) => {
        const headers = new Headers({ Accept: 'application/json', Authorization: `Bearer ${token}` })
        const body = request.body === undefined ? undefined : JSON.stringify(request.body)
        if (body !== undefined) headers.set('Content-Type', 'application/json')
        checkDeadline()

        let response: Response
        try {
          response = await fetch(new URL(base + request.path, window.location.origin), {
            method: request.method ?? 'GET',
            headers,
            body,
            signal,
            credentials: 'omit',
            cache: 'no-store',
            redirect: 'error',
            referrerPolicy: 'no-referrer',
          })
        } catch {
          checkDeadline()
          throw new ApiError('network')
        }

        checkDeadline()
        // Map the trusted HTTP status and keep arbitrary backend detail out of the UI.
        if (!response.ok) throw new ApiError('http', response.status)
        let json: unknown
        try {
          json = await response.json()
        } catch {
          checkDeadline()
          throw new ApiError('invalid-response')
        }

        checkDeadline()
        const parsed = request.schema.safeParse(json)
        checkDeadline()
        if (!parsed.success) throw new ApiError('invalid-response')
        return parsed.data
      })
    },
  }
}

export type ApiClient = ReturnType<typeof createApiClient>
