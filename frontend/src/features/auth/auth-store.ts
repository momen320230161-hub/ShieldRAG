import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import type { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../../lib/api/client'
import type { ApiClient, ApiRequest } from '../../lib/api/client'
import type { AuthGateway } from '../../lib/supabase/client'
import { profileSchema } from './schemas/auth'
import type { LoginInput, Profile } from './schemas/auth'

type AuthView =
  | { status: 'checking' }
  | { status: 'anonymous'; notice?: string }
  | { status: 'ready'; profile: Profile }
  | { status: 'denied' }
  | { status: 'unavailable'; message: string }

interface SessionScope {
  session: Session
  controller: AbortController
  afterRecovery: boolean
}

const expiredNotice = 'Your session expired. Sign in again to continue.'

export function createAuthStore(gateway: AuthGateway, api: ApiClient, cache: QueryClient) {
  let view: AuthView = { status: 'checking' }
  let current: SessionScope | undefined
  let refreshing: SessionScope | undefined
  let expiryTimer: ReturnType<typeof setTimeout> | undefined
  let attached = false
  let suppressSessions = false
  let signingOut = false
  const listeners = new Set<() => void>()

  function publish(value: AuthView) {
    view = value
    listeners.forEach((listener) => listener())
  }

  function clearScope() {
    current?.controller.abort()
    current = undefined
    clearTimeout(expiryTimer)
    cache.clear()
  }

  function isExpired(scope: SessionScope) {
    return (scope.session.expires_at ?? 0) * 1000 <= Date.now()
  }

  async function leave(notice?: string) {
    if (signingOut) return
    signingOut = true
    suppressSessions = true
    clearScope()
    publish({ status: 'checking' })
    try {
      const { error } = await gateway.auth.signOut({ scope: 'local' })
      if (error) throw error
    } catch {
      notice ??= 'Signed out of this browser. The authentication service could not confirm sign-out.'
    } finally {
      signingOut = false
      if (attached) publish({ status: 'anonymous', notice })
    }
  }

  async function recover(scope: SessionScope) {
    if (current !== scope || refreshing === scope) return
    if (scope.afterRecovery) {
      await leave(expiredNotice)
      return
    }
    refreshing = scope
    scope.controller.abort()
    clearTimeout(expiryTimer)
    cache.clear()
    publish({ status: 'checking' })
    try {
      const { data, error } = await gateway.auth.refreshSession()
      if (current !== scope) return
      if (error || !data.session || data.session.access_token === scope.session.access_token) {
        await leave(expiredNotice)
      } else {
        receiveSession('TOKEN_REFRESHED', data.session)
      }
    } catch {
      if (current === scope) await leave(expiredNotice)
    } finally {
      if (refreshing === scope) refreshing = undefined
    }
  }

  async function resolveProfile(scope: SessionScope) {
    if (current !== scope || scope.controller.signal.aborted) return
    if (isExpired(scope)) {
      await recover(scope)
      return
    }
    try {
      const profile = await cache.fetchQuery({
        queryKey: ['profile', scope.session.user.id],
        retry: false,
        queryFn: ({ signal }) => api.request({
          path: '/me', schema: profileSchema,
          signal: AbortSignal.any([signal, scope.controller.signal]),
        }, scope.session.access_token),
      })
      if (current !== scope || scope.controller.signal.aborted) return
      if (isExpired(scope)) {
        await recover(scope)
        return
      }
      if (profile.id !== scope.session.user.id) {
        publish({ status: 'denied' })
        return
      }
      scope.afterRecovery = false
      publish({ status: 'ready', profile })
    } catch (error) {
      if (current !== scope || scope.controller.signal.aborted) return
      if (error instanceof ApiError) {
        if (error.status === 401) {
          await recover(scope)
        } else if (error.status === 403 || error.status === 404 || error.kind === 'invalid-response') {
          publish({ status: 'denied' })
        } else {
          publish({ status: 'unavailable', message: error.message })
        }
      } else {
        publish({ status: 'unavailable', message: 'Could not verify your workspace access.' })
      }
    }
  }

  function receiveSession(event: AuthChangeEvent, session: Session | null) {
    if (!attached || suppressSessions) return
    if (event === 'TOKEN_REFRESHED' && refreshing && current !== refreshing &&
        session?.user.id === refreshing.session.user.id && current?.session.user.id !== session.user.id) {
      return
    }
    if (!session) {
      // An SDK refresh can emit SIGNED_OUT before its error result arrives.
      if (refreshing && current === refreshing) return
      clearScope()
      publish({
        status: 'anonymous',
        notice: event === 'SIGNED_OUT' ? 'Your session ended. Sign in again to continue.' : undefined,
      })
      return
    }
    if (current?.session.access_token === session.access_token && current.session.user.id === session.user.id) return

    clearScope()
    const scope: SessionScope = {
      session,
      controller: new AbortController(),
      afterRecovery: refreshing?.session.user.id === session.user.id,
    }
    current = scope
    publish({ status: 'checking' })
    const expiresIn = (session.expires_at ?? 0) * 1000 - Date.now()
    if (expiresIn > 0) {
      expiryTimer = setTimeout(() => void recover(scope), Math.min(expiresIn, 2_147_483_647))
    }
    // Schedule SDK work outside the SDK subscription callback and its lock.
    queueMicrotask(() => void resolveProfile(scope))
  }

  function checkExpiry() {
    if (current && isExpired(current)) void recover(current)
  }

  return {
    getSnapshot: () => view,
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    connect() {
      attached = true
      const { data } = gateway.auth.onAuthStateChange(receiveSession)
      window.addEventListener('focus', checkExpiry)
      document.addEventListener('visibilitychange', checkExpiry)
      return () => {
        attached = false
        data.subscription.unsubscribe()
        window.removeEventListener('focus', checkExpiry)
        document.removeEventListener('visibilitychange', checkExpiry)
        clearScope()
        refreshing = undefined
        view = { status: 'checking' }
      }
    },
    async signIn(input: LoginInput): Promise<string | undefined> {
      try {
        const { data, error } = await gateway.auth.signInWithPassword(input)
        if (error) {
          if (error.status === 429) return 'Too many sign-in attempts. Wait a moment and try again.'
          if (!error.status || error.status >= 500) return 'Cannot reach sign-in. Try again shortly.'
          return 'The email or password is incorrect.'
        }
        if (!data.session) return 'Sign-in did not complete. Try again.'
        if (suppressSessions && !signingOut) {
          suppressSessions = false
          receiveSession('SIGNED_IN', data.session)
        }
      } catch {
        return 'Cannot reach sign-in. Try again shortly.'
      }
    },
    signOut: () => leave(),
    retryProfile() {
      if (!current || view.status !== 'unavailable') return
      publish({ status: 'checking' })
      void resolveProfile(current)
    },
    async request<T>(input: ApiRequest<T>): Promise<T> {
      const scope = current
      if (!scope || view.status !== 'ready') throw new ApiError('http', 401)
      if (isExpired(scope)) {
        void recover(scope)
        throw new ApiError('http', 401)
      }
      const signals = [scope.controller.signal]
      if (input.signal) signals.push(input.signal)
      const signal = AbortSignal.any(signals)
      try {
        return await api.request({ ...input, signal }, scope.session.access_token)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401 && !signal.aborted) void recover(scope)
        throw error
      }
    },
  }
}

export type AuthStore = ReturnType<typeof createAuthStore>
