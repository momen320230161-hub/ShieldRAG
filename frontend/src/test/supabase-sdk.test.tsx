import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { createAuthGateway } from '../lib/supabase/client'
import { admin, mount, profilesByToken, session } from './auth-fixtures'
import { server } from './server'

it.each([204, 503])('signs in, restores, and clears local SDK state on logout HTTP %s', async (logoutStatus) => {
  const project = 'https://shieldrag-sdk.example.test'
  const key = 'sb_publishable_test_only'
  const access = session(admin, 'test-sdk-access')
  const login = vi.fn()
  const logout = vi.fn()
  server.use(
    http.post(`${project}/auth/v1/token`, async ({ request }) => {
      login(new URL(request.url).searchParams.get('grant_type'), request.headers.get('apikey'), await request.json())
      return HttpResponse.json(access)
    }),
    http.post(`${project}/auth/v1/logout`, ({ request }) => {
      logout(new URL(request.url).searchParams.get('scope'), request.headers.get('authorization'))
      if (logoutStatus === 204) return new HttpResponse(null, { status: 204 })
      return HttpResponse.json({ msg: 'private upstream failure' }, { status: logoutStatus })
    }),
  )
  profilesByToken({ 'test-sdk-access': admin })
  const first = createAuthGateway(project, key)
  const user = userEvent.setup()
  const initial = mount('/login?access_token=ignored', first)
  try {
    await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })
    await user.type(screen.getByRole('textbox', { name: 'Email address' }), 'assigned@example.test')
    await user.type(screen.getByLabelText('Password', { selector: 'input' }), 'test-only-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
    expect(login).toHaveBeenCalledExactlyOnceWith('password', key, expect.objectContaining({
      email: 'assigned@example.test', password: 'test-only-password',
    }))
  } finally {
    initial.unmount()
    await first.auth.dispose()
  }

  const next = createAuthGateway(project, key)
  const restored = mount('/admin', next)
  try {
    expect(await screen.findByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
    expect(login).toHaveBeenCalledTimes(1)
    await user.click(screen.getByLabelText('Account menu'))
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in to ShieldRAG' })).toBeVisible()
    if (logoutStatus === 503) {
      expect(screen.getByRole('alert')).toHaveTextContent('The authentication service could not confirm sign-out.')
    }
    expect(logout).toHaveBeenCalledExactlyOnceWith('local', 'Bearer test-sdk-access')
    expect(window.localStorage.getItem('shieldrag-auth-shieldrag-sdk.example.test')).toBeNull()
  } finally {
    restored.unmount()
    await next.auth.dispose()
  }
})
