import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { QueryClient } from '@tanstack/react-query'
import { act, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { App } from '../app/App'
import { createAuthStore } from '../features/auth/auth-store'
import type { Profile } from '../features/auth/schemas/auth'
import { createApiClient } from '../lib/api/client'
import type { AuthGateway } from '../lib/supabase/client'
import { backend, server } from './server'

export const student: Profile = {
  id: '00000000-0000-4000-8000-000000000001',
  role: 'student',
  email: 'student@example.test',
  display_name: 'Example Student',
}
export const admin: Profile = {
  id: '00000000-0000-4000-8000-000000000002',
  role: 'admin',
  email: null,
  display_name: 'Example Admin',
}

export function session(profile: Profile, accessToken: string, expiresIn = 300): Session {
  return {
    access_token: accessToken,
    refresh_token: 'test-only-refresh',
    token_type: 'bearer',
    expires_in: expiresIn,
    expires_at: Math.floor(Date.now() / 1000) + expiresIn,
    user: {
      id: profile.id, aud: 'authenticated', created_at: '2025-01-01T00:00:00Z',
      app_metadata: {}, user_metadata: { role: 'admin' },
    },
  }
}

export function mockAuth(initial: Session | null) {
  type Callback = (event: AuthChangeEvent, value: Session | null) => void
  let receive: Callback | undefined
  const auth: AuthGateway = {
    auth: {
      onAuthStateChange(callback: Callback) {
        receive = callback
        queueMicrotask(() => {
          if (receive === callback) receive('INITIAL_SESSION', initial)
        })
        return { data: { subscription: { id: 'test', callback, unsubscribe: () => { receive = undefined } } } }
      },
      signInWithPassword: vi.fn(),
      signOut: vi.fn(async () => {
        receive?.('SIGNED_OUT', null)
        return { error: null }
      }),
      refreshSession: vi.fn(async () => ({ data: { session: null, user: null }, error: null })),
    },
  }
  return {
    gateway: auth,
    emit: (event: AuthChangeEvent, value: Session | null) => act(() => receive?.(event, value)),
    loginAs(value: Session) {
      vi.mocked(auth.auth.signInWithPassword).mockImplementation(async () => {
        receive?.('SIGNED_IN', value)
        return { data: { session: value, user: value.user }, error: null }
      })
    },
  }
}

export function mount(path: string, gateway: AuthGateway) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const store = createAuthStore(gateway, createApiClient('/api/v1'), cache)
  const rendered = render(<MemoryRouter initialEntries={[path]}><App cache={cache} store={store} /></MemoryRouter>)
  return { cache, store, ...rendered }
}

export function profilesByToken(entries: Record<string, Profile>) {
  server.use(http.get(`${backend}/me`, ({ request }) => {
    const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
    const profile = entries[token]
    return profile ? HttpResponse.json(profile) : HttpResponse.json({}, { status: 401 })
  }))
}
