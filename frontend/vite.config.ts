import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readEnvironment } from './src/lib/config/environment.ts'

export default defineConfig(({ mode }) => {
  const publicKeys = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_API_BASE_URL']
  const env = loadEnv(mode, process.cwd(), [...publicKeys, 'BACKEND_PROXY_TARGET'])
  const target = env.BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000'
  const config = readEnvironment({
    supabaseUrl: env.VITE_SUPABASE_URL ?? '',
    publishableKey: env.VITE_SUPABASE_PUBLISHABLE_KEY ?? '',
    apiBase: env.VITE_API_BASE_URL ?? '',
  })

  return {
    // Invalid values are omitted at build time, including a secret pasted into a public field.
    envPrefix: [],
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(config?.supabaseUrl ?? ''),
      'import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY': JSON.stringify(config?.publishableKey ?? ''),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(config?.apiBase ?? ''),
    },
    plugins: [react(), tailwindcss()],
    build: {
      rolldownOptions: {
        output: {
          codeSplitting: { groups: [{ name: 'supabase', test: /node_modules[\\/]@supabase[\\/]/ }] },
        },
      },
    },
    server: {
      host: '127.0.0.1',
      proxy: { '^/api/v1(?:/|$)': { target, changeOrigin: true }, '/health': { target, changeOrigin: true } },
    },
  }
})
