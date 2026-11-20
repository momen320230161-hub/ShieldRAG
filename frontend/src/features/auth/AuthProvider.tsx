import { createContext, useContext, useEffect, useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import type { AuthStore } from './auth-store'

const AuthContext = createContext<AuthStore | null>(null)

export function AuthProvider({ store, children }: { store: AuthStore; children: ReactNode }) {
  useEffect(() => store.connect(), [store])
  return <AuthContext.Provider value={store}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const store = useContext(AuthContext)
  if (!store) throw new Error('Missing authentication provider.')
  const view = useSyncExternalStore(store.subscribe, store.getSnapshot)
  return { view, store }
}
