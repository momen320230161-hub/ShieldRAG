# Testing

Run from `backend/` after installing the lockfile:

```powershell
.venv/Scripts/python -m pytest -q -m 'not integration'
```

These tests use only HTTPX mock transports and synthetic data. They cover configuration validation, startup/health, bearer failures, delegated JWT rejection, trusted roles, escalation attempts, Admin dependency, public/restricted documents, pending/rejected isolation, event ownership, pagination, sanitized errors, and token separation. No Supabase credentials are required.

For real, read-only Auth and PostgREST HTTP tests, configure `.env` and opt in:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
.venv/Scripts/python -m pytest -q -m integration
```

Three tests require no user token: Auth health, anonymous table-access denial, and rejection of a forged JWT. Successful account tests also require `SHIELDRAG_STUDENT_TOKEN` and `SHIELDRAG_ADMIN_TOKEN` environment variables, obtained from existing synthetic accounts via Supabase Auth. Never put tokens on the command line, in commits, or in CI logs. Without these tokens, those two tests explicitly skip. A complete positive Auth/RBAC HTTP acceptance run requires both roles; mock tests and SQL role simulation alone do not establish successful user JWT acceptance.

For live database policy verification, an authorized operator can run `backend/tests/rls_rollback.sql` through a Supabase SQL connection. It creates temporary synthetic Auth users, documents, chunks, and events inside a transaction; exercises Student/Admin RLS and denied writes; raises an exception on a failed assertion; then rolls back all fixtures. If an assertion fails, roll back/close the transaction before continuing. Do not change this script to commit on the existing cloud project.

An actual Uvicorn smoke check is also useful:

```powershell
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# In another terminal:
Invoke-RestMethod http://127.0.0.1:8000/health
```

Verification results and remaining account-token blockers are recorded in the implementation PR. `/health` is liveness only; use the integration tests to establish real cloud connectivity.
