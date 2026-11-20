import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClient } from '@tanstack/react-query'
import '@fontsource-variable/instrument-sans'
import './styles/index.css'
import { App } from './app/App'
import { FeedbackPage } from './components/ui/Feedback'
import { createAuthStore } from './features/auth/auth-store'
import { createApiClient } from './lib/api/client'
import { readEnvironment } from './lib/config/environment'
import { createAuthGateway } from './lib/supabase/client'

const config = readEnvironment({
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL,
  publishableKey: import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
  apiBase: import.meta.env.VITE_API_BASE_URL,
})
const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Missing application root.')
const root = createRoot(rootElement)

if (!config) {
  root.render(
    <FeedbackPage title="ShieldRAG is not configured">
      <p>Ask your administrator to check the public Supabase URL, publishable key and API path.</p>
    </FeedbackPage>,
  )
} else {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const gateway = createAuthGateway(config.supabaseUrl, config.publishableKey)
  const store = createAuthStore(gateway, createApiClient(config.apiBase), cache)
  root.render(
    <StrictMode>
      <BrowserRouter>
        <App store={store} cache={cache} />
      </BrowserRouter>
    </StrictMode>,
  )
}
