import { createClient } from '@supabase/supabase-js'
import type { SupabaseClient } from '@supabase/supabase-js'

export interface AuthGateway {
  auth: Pick<SupabaseClient['auth'],
    'onAuthStateChange' | 'signInWithPassword' | 'signOut' | 'refreshSession'>
}

export function createAuthGateway(projectUrl: string, publishableKey: string) {
  const storageKey = `shieldrag-auth-${new URL(projectUrl).host}`
  const { auth } = createClient(projectUrl, publishableKey, {
    auth: { storageKey, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  })

  return { auth } satisfies AuthGateway
}
