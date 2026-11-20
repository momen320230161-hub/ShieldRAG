# ShieldRAG frontend

Task 07.1 provides password sign-in and protected Student and Admin dashboard shells. The dashboards describe future workflows as upcoming.

## Local development

Use Node.js 24 and the repository's locked Python 3.12 environment. Run both terminals from the repository root.

### Terminal 1 — FastAPI

Configure `backend/.env` as described in [backend setup](../docs/backend-setup.md), then start the API.

```powershell
Set-Location backend
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — React

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm ci
```

Set `VITE_SUPABASE_PUBLISHABLE_KEY` in `.env.local` to the project's publishable key from the Supabase dashboard under **Connect** or **Settings → API Keys**. The Supabase URL must match the backend project. Keep the backend's `.env`, service key, Gemini key and database credentials outside the frontend.

```powershell
npm run dev
```

Open the loopback URL Vite prints, typically `http://127.0.0.1:5173`. Sign in with an already provisioned Student or Admin account whose role profile exists. A healthy proxy responds to `/health` with `{"status":"ok"}`. Without a session, `/api/v1/me` returns 401.

| Setting | Purpose |
| --- | --- |
| `VITE_SUPABASE_URL` | Public HTTPS project origin. Loopback HTTP is supported for local Supabase. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Modern public key beginning with `sb_publishable_`. |
| `VITE_API_BASE_URL` | Same-origin API prefix. Defaults to `/api/v1`. A custom prefix needs a corresponding proxy route. |
| `BACKEND_PROXY_TARGET` | Vite's development-only backend origin. Defaults to `http://127.0.0.1:8000`. |

## Checks

```text
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
npm run check:bundle
```

Tests mock Auth and FastAPI responses, with no live accounts or provider calls. The build also works without configuration for offline checks. In that case the app shows setup guidance. See [architecture](../docs/frontend-architecture.md) and [authentication](../docs/frontend-authentication.md).
