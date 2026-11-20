import { QueryClientProvider } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { AuthProvider } from '../features/auth/AuthProvider'
import type { AuthStore } from '../features/auth/auth-store'
import { AppRoutes } from './router'

export function App({ store, cache }: { store: AuthStore; cache: QueryClient }) {
  return (
    <QueryClientProvider client={cache}>
      <AuthProvider store={store}>
        <AppRoutes />
      </AuthProvider>
    </QueryClientProvider>
  )
}
