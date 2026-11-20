import { AuthApiError } from '@supabase/supabase-js'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { profileSchema } from '../features/auth/schemas/auth'
import { admin, mockAuth, mount, profilesByToken, session, student } from './auth-fixtures'
import { backend, server } from './server'

const studentSession = () => session(student, 'student-access')
const adminSession = () => session(admin, 'admin-access')

async function fillLogin(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox', { name: 'Email address' }), student.email!)
  await user.type(screen.getByLabelText('Password', { selector: 'input' }), 'synthetic-password')
}

describe('login and routing', () => {
  it('redirects anonymous deep links to login and validates required fields', async () => {
    const { gateway } = mockAuth(null)
    mount('/admin?role=admin&access_token=untrusted-fragment', gateway)
    const submit = await screen.findByRole('button', { name: 'Sign in' })
    await userEvent.setup().click(submit)
    expect(await screen.findByText('Enter a valid email address.')).toBeVisible()
    expect(screen.getByText('Enter your password.')).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'Email address' })).toBeInvalid()
    expect(gateway.auth.signInWithPassword).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).toBeNull()
  })

  it('supports keyboard traversal and password visibility with an accessible label', async () => {
    const { gateway } = mockAuth(null)
    mount('/login', gateway)
    await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })
    const user = userEvent.setup()
    await user.tab()
    expect(screen.getByRole('textbox', { name: 'Email address' })).toHaveFocus()
    await user.tab()
    const field = screen.getByLabelText('Password', { selector: 'input' })
    expect(field).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Show password' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(field).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toBeVisible()
  })

  it('signs in once, waits for the backend profile, and routes to the trusted role', async () => {
    const auth = mockAuth(null)
    const allowLogin = Promise.withResolvers<void>()
    const profileRequested = Promise.withResolvers<void>()
    const allowProfile = Promise.withResolvers<void>()
    const value = studentSession()
    vi.mocked(auth.gateway.auth.signInWithPassword).mockImplementation(async () => {
      await allowLogin.promise
      auth.emit('SIGNED_IN', value)
      return { data: { session: value, user: value.user }, error: null }
    })
    server.use(http.get(`${backend}/me`, async () => {
      profileRequested.resolve()
      await allowProfile.promise
      return HttpResponse.json(student)
    }))
    mount('/login', auth.gateway)
    await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })
    const user = userEvent.setup()
    await fillLogin(user)
    await user.dblClick(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled()
    expect(auth.gateway.auth.signInWithPassword).toHaveBeenCalledExactlyOnceWith({
      email: student.email, password: 'synthetic-password',
    })

    allowLogin.resolve()
    await profileRequested.promise
    expect(await screen.findByRole('status')).toHaveTextContent('Checking workspace access')
    expect(screen.queryByRole('heading', { name: /dashboard/i })).toBeNull()
    allowProfile.resolve()
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).toBeNull()
  })

  it.each([
    [400, 'The email or password is incorrect.'],
    [503, 'Cannot reach sign-in. Try again shortly.'],
  ])('sanitizes sign-in errors with status %s and removes the password', async (status, message) => {
    const { gateway } = mockAuth(null)
    vi.mocked(gateway.auth.signInWithPassword).mockResolvedValue({
      data: { session: null, user: null },
      error: new AuthApiError('private upstream diagnostic test token', status, 'unexpected_failure'),
    })
    mount('/login', gateway)
    await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })
    const user = userEvent.setup()
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByLabelText('Password', { selector: 'input' })).toHaveValue('')
    expect(screen.queryByText(/upstream diagnostic/)).toBeNull()
  })

  it.each([
    ['/student', student, 'student-access', 'Student dashboard'],
    ['/admin', admin, 'admin-access', 'Admin dashboard'],
    ['/login', admin, 'admin-access', 'Admin dashboard'],
  ] as const)('restores the trusted session at %s on reload', async (path, profile, token, heading) => {
    profilesByToken({ [token]: profile })
    const first = mount(path, mockAuth(session(profile, token)).gateway)
    expect(screen.getByRole('status')).toBeVisible()
    expect(await screen.findByRole('heading', { name: heading })).toBeVisible()
    first.unmount()
    mount(path, mockAuth(session(profile, token)).gateway)
    expect(screen.getByRole('status')).toBeVisible()
    expect(await screen.findByRole('heading', { name: heading })).toBeVisible()
  })

  it('denies Student access to /admin even with conflicting client role hints', async () => {
    profilesByToken({ 'student-access': student })
    mount('/admin?role=admin', mockAuth(studentSession()).gateway)
    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).toBeNull()
    await userEvent.setup().click(screen.getByRole('link', { name: 'Go to my dashboard' }))
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
  })

  it('shows a 404 for an unknown route', async () => {
    mount('/a-missing-route', mockAuth(null).gateway)
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Go to workspace' })).toHaveAttribute('href', '/')
    await screen.findByRole('heading', { name: 'Page not found' })
  })

  it('toggles the responsive navigation and clears trusted state on logout', async () => {
    profilesByToken({ 'student-access': student })
    const { gateway } = mockAuth(studentSession())
    const { cache } = mount('/student', gateway)
    await screen.findByRole('heading', { name: 'Student dashboard' })
    const user = userEvent.setup()
    const disclosure = screen.getByRole('button', { name: 'Open navigation' })
    expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    await user.click(disclosure)
    expect(screen.getByRole('button', { name: 'Close navigation' })).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('link', { name: 'Overview' }))
    expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    cache.setQueryData(['student-data'], 'test-user-specific-data')
    await user.click(screen.getByLabelText('Account menu'))
    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })).toBeVisible()
    expect(cache.getQueryData(['student-data'])).toBeUndefined()
    expect(screen.queryByText('Example Student')).toBeNull()
    expect(gateway.auth.signOut).toHaveBeenCalledExactlyOnceWith({ scope: 'local' })
  })
})

describe('profile trust and session changes', () => {
  it.each([
    [403, { detail: 'private upstream profile error' }],
    [404, { detail: 'missing' }],
    [200, { ...student, role: 'owner' }],
    [200, { ...student, role: undefined }],
    [200, { ...student, id: 'malformed-id' }],
    [200, admin],
  ])('denies access on an unavailable or untrusted profile (%s)', async (status, profile) => {
    server.use(http.get(`${backend}/me`, () => HttpResponse.json(profile as never, { status })))
    mount('/admin', mockAuth(studentSession()).gateway)
    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).toBeNull()
    expect(screen.queryByText(/upstream profile error/)).toBeNull()
  })

  it('handles backend 503 without signing out, and verifies the profile on manual retry', async () => {
    server.use(http.get(`${backend}/me`, () => HttpResponse.json({ detail: 'private text' }, { status: 503 })))
    const { gateway } = mockAuth(studentSession())
    mount('/student', gateway)
    expect(await screen.findByRole('alert')).toHaveTextContent('The service is temporarily unavailable.')
    expect(screen.queryByRole('heading', { name: 'Student dashboard' })).toBeNull()
    expect(gateway.auth.signOut).not.toHaveBeenCalled()
    profilesByToken({ 'student-access': student })
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
  })

  it('keeps a timed-out profile protected, preserves the session, and retries only on request', async () => {
    const { gateway } = mockAuth(studentSession())
    const started = Promise.withResolvers<void>()
    const late = Promise.withResolvers<Response>()
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => {
      started.resolve()
      return late.promise
    }).mockResolvedValueOnce(Response.json(student))

    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] })
    try {
      mount('/student', gateway)
      await act(async () => { await started.promise })
      expect(screen.getByRole('status')).toBeVisible()
      expect(screen.queryByRole('heading', { name: 'Student dashboard' })).toBeNull()
      await act(() => vi.advanceTimersByTimeAsync(12_000))
      expect(screen.getByRole('alert')).toHaveTextContent('The request took too long.')
      expect(screen.queryByRole('heading', { name: 'Student dashboard' })).toBeNull()
      expect(fetch).toHaveBeenCalledTimes(1)
      expect(gateway.auth.signOut).not.toHaveBeenCalled()
      expect(gateway.auth.refreshSession).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }

    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    await act(async () => { late.resolve(Response.json(admin)) })
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    expect(gateway.auth.signOut).not.toHaveBeenCalled()
  })

  it('refreshes an expired restored session before sending any backend request', async () => {
    const auth = mockAuth(session(student, 'expired-access', -1))
    const fresh = studentSession()
    vi.mocked(auth.gateway.auth.refreshSession).mockResolvedValue({
      data: { session: fresh, user: fresh.user }, error: null,
    })
    const seen = vi.fn()
    server.use(http.get(`${backend}/me`, ({ request }) => {
      seen(request.headers.get('authorization'))
      return HttpResponse.json(student)
    }))
    mount('/student', auth.gateway)
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    expect(auth.gateway.auth.refreshSession).toHaveBeenCalledTimes(1)
    expect(seen).toHaveBeenCalledExactlyOnceWith('Bearer student-access')
  })

  it('hides an expired dashboard immediately and returns to login on refresh failure', async () => {
    profilesByToken({ 'student-access': student })
    const value = studentSession()
    const { gateway } = mockAuth(value)
    const refresh = Promise.withResolvers<Awaited<ReturnType<typeof gateway.auth.refreshSession>>>()
    vi.mocked(gateway.auth.refreshSession).mockReturnValue(refresh.promise)
    mount('/student', gateway)
    await screen.findByRole('heading', { name: 'Student dashboard' })
    vi.spyOn(Date, 'now').mockReturnValue((value.expires_at! + 1) * 1000)
    act(() => window.dispatchEvent(new Event('focus')))
    expect(screen.queryByRole('heading', { name: 'Student dashboard' })).toBeNull()
    expect(screen.getByRole('status')).toBeVisible()
    refresh.resolve({
      data: { session: null, user: null },
      error: new AuthApiError('private refresh token', 400, 'refresh_token_not_found'),
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session expired.')
    expect(screen.queryByText(/private refresh token/)).toBeNull()
  })

  it('handles a rejected refreshed token without an auth retry loop', async () => {
    server.use(http.get(`${backend}/me`, () => HttpResponse.json({}, { status: 401 })))
    const auth = mockAuth(studentSession())
    const refreshed = session(student, 'renewed-access')
    vi.mocked(auth.gateway.auth.refreshSession).mockResolvedValue({
      data: { session: refreshed, user: refreshed.user }, error: null,
    })
    mount('/', auth.gateway)
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session expired.')
    expect(auth.gateway.auth.refreshSession).toHaveBeenCalledTimes(1)
  })

  it('clears cached data and ignores a stale Admin result after an account switch', async () => {
    const started = Promise.withResolvers<void>()
    const finish = Promise.withResolvers<void>()
    server.use(http.get(`${backend}/me`, async ({ request }) => {
      if (request.headers.get('authorization') === 'Bearer admin-access') {
        started.resolve()
        await finish.promise
        return HttpResponse.json(admin)
      }
      return HttpResponse.json(student)
    }))
    const auth = mockAuth(adminSession())
    const { cache, store } = mount('/', auth.gateway)
    await started.promise
    cache.setQueryData(['old-user'], { private: true })
    auth.emit('SIGNED_IN', studentSession())
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    await act(async () => { finish.resolve() })
    expect(cache.getQueryData(['old-user'])).toBeUndefined()
    expect(cache.getQueryData(['profile', admin.id])).toBeUndefined()
    expect(store.getSnapshot()).toEqual({ status: 'ready', profile: student })
  })

  it('cancels authenticated requests on logout and ignores a late session event', async () => {
    profilesByToken({ 'student-access': student })
    const auth = mockAuth(studentSession())
    const { store } = mount('/student', auth.gateway)
    await screen.findByRole('heading', { name: 'Student dashboard' })
    const started = Promise.withResolvers<void>()
    const finish = Promise.withResolvers<void>()
    server.use(http.get(`${backend}/me`, async () => {
      started.resolve()
      await finish.promise
      return HttpResponse.json(student)
    }))
    const request = store.request({ path: '/me', schema: profileSchema })
    const rejected = expect(request).rejects.toMatchObject({ name: 'AbortError' })
    await started.promise
    await act(() => store.signOut())
    auth.emit('TOKEN_REFRESHED', studentSession())
    finish.resolve()
    await rejected
    expect(await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })).toBeVisible()
    expect(store.getSnapshot().status).toBe('anonymous')
  })

  it('clears protected state on a remote logout failure and allows sign-in again', async () => {
    profilesByToken({ 'student-access': student })
    const auth = mockAuth(studentSession())
    vi.mocked(auth.gateway.auth.signOut).mockResolvedValue({
      error: new AuthApiError('private logout error', 503, 'unexpected_failure'),
    })
    const { store } = mount('/', auth.gateway)
    await screen.findByRole('heading', { name: 'Student dashboard' })
    await act(() => store.signOut())
    expect(await screen.findByRole('alert')).toHaveTextContent('Signed out of this browser.')
    auth.emit('TOKEN_REFRESHED', studentSession())
    expect(store.getSnapshot().status).toBe('anonymous')

    auth.loginAs(studentSession())
    const user = userEvent.setup()
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Student dashboard' })).toBeVisible()
  })

  it('uses one refresh for simultaneous API 401s and does not replay requests', async () => {
    profilesByToken({ 'student-access': student })
    const auth = mockAuth(studentSession())
    const { store } = mount('/student', auth.gateway)
    await screen.findByRole('heading', { name: 'Student dashboard' })
    const reply = Promise.withResolvers<void>()
    const waiting = Promise.withResolvers<void>()
    const renewed = session(student, 'renewed-access')
    vi.mocked(auth.gateway.auth.refreshSession).mockImplementation(async () => {
      await reply.promise
      return { data: { session: renewed, user: renewed.user }, error: null }
    })
    const hits = vi.fn()
    server.use(http.get(`${backend}/me`, async ({ request }) => {
      if (request.headers.get('authorization') === 'Bearer renewed-access') return HttpResponse.json(student)
      hits()
      if (hits.mock.calls.length === 2) waiting.resolve()
      await waiting.promise
      return HttpResponse.json({}, { status: 401 })
    }))
    const request = { path: '/me', schema: profileSchema }
    await act(async () => {
      await Promise.allSettled([store.request(request), store.request(request)])
    })
    expect(store.getSnapshot().status).toBe('checking')
    expect(hits).toHaveBeenCalledTimes(2)
    expect(auth.gateway.auth.refreshSession).toHaveBeenCalledTimes(1)
    reply.resolve()
    await waitFor(() => expect(store.getSnapshot().status).toBe('ready'))
    expect(hits).toHaveBeenCalledTimes(2)
  })
})
