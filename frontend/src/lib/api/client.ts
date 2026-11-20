import type { ZodType } from 'zod'
import { isApiPath } from '../config/environment'

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

export class ApiError extends Error {
  constructor(
    readonly kind: 'http' | 'network' | 'invalid-response',
    readonly status?: number,
  ) {
    super(
      kind === 'http' && status !== undefined
        ? statusMessages[status] ?? 'The service could not complete this request.'
        : kind === 'network'
          ? 'Could not reach the service. Check your connection and try again.'
          : 'The service returned an unexpected response.',
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
}

export function createApiClient(base: string) {
  if (!isApiPath(base)) throw new TypeError('Invalid API base.')

  return {
    async request<T>(request: ApiRequest<T>, token: string): Promise<T> {
      if (!isApiPath(request.path)) throw new TypeError('Invalid API path.')
      const signals = [AbortSignal.timeout(12_000)]
      if (request.signal) signals.push(request.signal)
      const signal = AbortSignal.any(signals)
      const headers = new Headers({ Accept: 'application/json', Authorization: `Bearer ${token}` })
      const body = request.body === undefined ? undefined : JSON.stringify(request.body)
      if (body !== undefined) headers.set('Content-Type', 'application/json')

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
        request.signal?.throwIfAborted()
        throw new ApiError('network')
      }

      // Map the trusted HTTP status and keep arbitrary backend detail out of the UI.
      if (!response.ok) throw new ApiError('http', response.status)
      let json: unknown
      try {
        json = await response.json()
      } catch {
        request.signal?.throwIfAborted()
        if (signal.aborted) throw new ApiError('network')
        throw new ApiError('invalid-response')
      }

      request.signal?.throwIfAborted()
      const parsed = request.schema.safeParse(json)
      if (!parsed.success) throw new ApiError('invalid-response')
      return parsed.data
    },
  }
}

export type ApiClient = ReturnType<typeof createApiClient>
