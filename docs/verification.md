# Task 02.1 verification — 2026-11-14

- Final complete pytest run: **86 passed, 0 skipped** (73 mocked/unit/orchestration tests, 13 real cloud integration tests).
- Real password authentication succeeded for fresh Student and Admin accounts. Their genuine Supabase JWTs passed FastAPI verification; trusted roles came from profiles despite both accounts claiming Admin in user metadata.
- Invalid and signature-tampered JWTs returned 401 with a Bearer challenge. Live verification found that Supabase reports invalid JWTs as 403 with `error_code=bad_jwt`; the gateway now classifies that as authentication failure while preserving permission 403s.
- FastAPI and direct PostgREST checks confirmed Student approved-public access, denied restricted content, Admin approved-restricted access, and pending/rejected chunk exclusion. RPC tests required exact positive fixture results as well as negative isolation.
- A Student profile-promotion attempt did not change persisted role; an independent Admin read and subsequent FastAPI identity check confirmed denial.
- Existing rollback-only SQL assertions passed, including event ownership and denied Student approval writes.
- Two synthetic fixture runs completed guarded SQL cleanup with **remaining_fixture_rows = 0**. Password manifests were removed locally afterward; generated SQL remains ignored. Synthetic sessions were logged out.
- `pip check` reported no broken requirements. The live Supabase security advisor reported no findings. Original migrations, schema, policies, existing commits, and non-fixture rows were preserved.
- A real Uvicorn process started successfully and returned `200 {"status":"ok"}` over local HTTP; the temporary process was then stopped.

## Reproduction

See [exact commands and provisioning/cleanup procedures](testing.md). The final full-suite command ran from `backend/` after applying generated setup SQL through the connected Supabase SQL operator:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = '.integration/final/manifest.json'
.venv/Scripts/python -m pytest -q -p no:cacheprovider
.venv/Scripts/python -m pip check
```

The matching cleanup SQL then returned zero remaining fixture rows and the local manifest was deleted. Those credentials no longer exist; generate a fresh run to reproduce.

## Skips, blockers, and limitations

No tests were skipped in the final full run. No blocker remains for real Student/Admin authentication verification. Opting out of integration intentionally skips live checks; basic live mode without fixtures skips ten account/content checks and is not full acceptance.

Native `psql` is not installed here. Its one-command runner was unit-tested for success, setup/test failure, and cleanup failure; real SQL/HTTP checks used the documented connected-SQL-operator alternative. One upstream test-client `anyio.abc.BlockingPortal` deprecation warning remains.

The fixture adapter depends on the inspected managed Auth schema and requires review after platform upgrades. Setup commits temporarily for cross-connection HTTP visibility; interrupted runs may require manual guarded cleanup. Auth audit records follow platform retention. Instant stolen-token revocation, production deployment controls, dependency vulnerability auditing, ingestion, Gemini, generation, and the AI Security Agent are outside this task's verified scope.

## Git delivery and prior results

Remote `main` was established at preserved implementation commit `66aba0e`; hardening is proposed separately on `feat/backend-hardening-verification`. No automatic merge or history rewrite occurred. See [Git workflow](git-workflow.md).

Task 02 previously reported 35 passes and two skipped successful-authentication tests. Task 02.1 replaces those token-only checks with real password/JWT/RLS/RPC verification and resolves that evidence gap.
