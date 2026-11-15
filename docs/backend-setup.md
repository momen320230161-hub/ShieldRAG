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

Open http://127.0.0.1:8000/docs. `GET /health` returns `200 {"status":"ok"}`. This is a liveness endpoint, not a database readiness check. Missing or invalid required configuration fails startup. Settings resolve `.env` paths relative to the repository, independent of the launch directory: process environment variables take priority, then `backend/.env`, then root `.env`. A setting omitted from `backend/.env` can come from root `.env`; an explicitly empty backend value overrides the root value. Keep all real keys outside Git.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | Yes | HTTPS project origin; existing project is `https://bnehmoxpzycxnsdxxfxc.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Yes | Modern `sb_publishable_...` key, sent as `apikey` |
| `SUPABASE_SECRET_KEY` | For ingestion/review/indexing | Modern `sb_secret_...` server key for private Storage and service-role-only write RPCs; never used for user-scoped reads |
| `GEMINI_API_KEY` | For RAG | Server-only Gemini Developer API key for document/query embeddings and generation |
| `GEMINI_EMBEDDING_MODEL` | Default supplied | `gemini-embedding-001` |
| `GEMINI_EMBEDDING_DIMENSIONS` | Fixed | `768`; other dimensions fail configuration validation |
| `GEMINI_GENERATION_MODEL` | Default supplied | `gemini-3.5-flash-lite`, verified using this project's key |
| `RAG_SIMILARITY_THRESHOLD` | Default supplied | `0.35`; calibrate with authorized synthetic evaluation |
| `RAG_DEFAULT_TOP_K` | Default supplied | `5`, range 1–10 |

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

See [document ingestion](document-ingestion.md) for Task 03 upload/metadata/approval routes, validation, the already-applied forward migration, and failure recovery. Missing server credentials leave read routes available and document writes disabled with 503. No Storage object is made public.

See [baseline RAG](rag.md) for all bounded extraction/chunk/index settings, external-transfer authorization and Swagger indexing/asking steps. A missing Gemini key leaves metadata/read routes available and RAG returns sanitized 503. Configure the key privately; do not overwrite an existing private `.env` when updating example settings.
