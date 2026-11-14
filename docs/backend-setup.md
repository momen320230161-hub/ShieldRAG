# Backend setup

From PowerShell at the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock
Copy-Item .env.example .env
# Edit .env and supply the publishable key from your Supabase dashboard.
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs. `GET /health` returns `200 {"status":"ok"}`. This is a liveness endpoint, not a database readiness check. Missing or invalid configuration fails startup. Commands run from `backend/` so the `.env` path is predictable.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | Yes | HTTPS project origin; existing project is `https://bnehmoxpzycxnsdxxfxc.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Yes | Modern `sb_publishable_...` key, sent as `apikey` |
| `SUPABASE_SECRET_KEY` | No | Reserved for future explicitly authorized server jobs; never used here |
| `GEMINI_API_KEY` | No | Reserved for future generation; never used here |

Settings mask keys in their representation. Never commit real keys, `.env`, tokens, passwords, or session files. Dependencies are pinned directly in `requirements.txt` and fully resolved in `requirements.lock` for Python 3.12 on Windows. Rebuild and review the lock when upgrading dependencies.

For Swagger authentication, use an existing synthetic Supabase account. Run:

```powershell
.venv/Scripts/python -m scripts.authenticate
```

This prompts for email and a hidden password, signs in directly with Supabase Auth, and saves only the access token in ignored `.env.auth-test`. Open this private file locally and paste its value into Swagger's **Authorize** dialog (the bearer value only). Delete the file after testing. No password database or backend password endpoint is introduced. Sign-in may require completing the project's configured email verification or MFA flow first; this simple password helper does not implement MFA.

For a CLI request without printing the token:

```powershell
$tokenLine = Get-Content .env.auth-test
$accessToken = $tokenLine.Substring('SHIELDRAG_ACCESS_TOKEN='.Length)
Invoke-RestMethod http://127.0.0.1:8000/api/v1/me -Headers @{ Authorization = "Bearer $accessToken" }
```

Bind locally for development. A deployed service needs HTTPS, controlled network access, request rate limits, and logs configured to exclude authorization headers and response bodies containing credentials. CORS is not enabled for a frontend in this task.
