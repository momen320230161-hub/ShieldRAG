function projectOrigin(value: string): string | undefined {
  try {
    const url = new URL(value)
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if (
      (url.protocol === 'https:' || (local && url.protocol === 'http:')) &&
      url.pathname === '/' && !url.username && !url.password && !url.search && !url.hash
    ) {
      return url.origin
    }
  } catch {
    return undefined
  }
}

export function isApiPath(value: string) {
  return /^\/(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_-]+$/.test(value)
}

export function readEnvironment(values: {
  supabaseUrl: string
  publishableKey: string
  apiBase: string
}) {
  const supabaseUrl = projectOrigin(values.supabaseUrl)
  if (!supabaseUrl || !/^sb_publishable_[A-Za-z0-9_-]+$/.test(values.publishableKey)) return null
  const apiBase = values.apiBase || '/api/v1'
  if (!isApiPath(apiBase)) return null

  return { supabaseUrl, publishableKey: values.publishableKey, apiBase }
}
