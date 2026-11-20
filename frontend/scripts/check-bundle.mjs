import { readdir, readFile } from 'node:fs/promises'
import { extname, join } from 'node:path'

const denied = [
  /sb_secret_[A-Za-z0-9_-]{16,}/,
  /AIza[A-Za-z0-9_-]{35}/,
  /eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/,
  /BACKEND_PROXY_TARGET|GEMINI_API_KEY|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SECRET_KEY/,
  /shieldrag-private-ci-canary|proxy-canary\.invalid/,
]

async function scan(folder) {
  let checked = 0
  for (const item of await readdir(folder, { withFileTypes: true })) {
    const path = join(folder, item.name)
    if (item.isDirectory()) {
      checked += await scan(path)
    } else if (['.js', '.css', '.html', '.json', '.map'].includes(extname(item.name))) {
      const contents = await readFile(path, 'utf8')
      if (denied.some((pattern) => pattern.test(contents))) {
        throw new Error(`Backend credential or private configuration pattern in ${path}`)
      }
      checked += 1
    }
  }
  return checked
}

const count = await scan('dist')
if (!count) throw new Error('No built frontend assets found.')
console.log(`Checked ${count} frontend assets for backend credential and private configuration patterns.`)
