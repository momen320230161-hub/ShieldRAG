# Task 03.1 verification — 2026-11-15

## Current final results

- Complete suite: **158 passed, 0 skipped** in 60.24 seconds: **137 mocked/unit/orchestration tests and 21 real Supabase integration tests**. Existing upload, successful review, Auth, RLS, pending/rejected isolation and restricted/vector-RPC checks remain passing.
- Actual upload and deliberate Storage tampering produced HTTP 409, kept the document pending with no reviewer, and persisted exactly one `document_integrity_failure / deny / SHA-256 mismatch detected` event with the authenticated Admin reviewer ID and affected document ID. The event contains only the declared audit fields, not content or sensitive request data.
- A real missing-object check also returned 409 and persisted the fixed missing-object event. Generic infrastructure errors remain service failures rather than confirmed integrity events.
- The fault-injected live test forwarded real Supabase traffic, dropped one successful audit response after commit, and observed two backend write attempts using one UUID and exactly one persisted row. Additional real server-RPC replays preserved that single row; reusing its ID for another document returned a conflict.
- Real Student and Admin user JWTs were denied direct audit RPC execution and event insertion. Attempts to update the event did not change it; an independent Admin read verified its exact original fields. Unauthorized Student approval created no integrity event.
- Unit tests passed for failed database writes, unavailable audit service, malformed/lost acknowledgements, static event fields, forbidden client fields, other confirmed integrity failures and pending-state preservation. An unconfirmed audit returns 503 and never invokes successful approval.
- `tests/integrity_audit_rollback.sql` passed against the actual database: trusted actor and document association, fixed failure kinds, mismatch evidence, deduplication, user-write denial, and unchanged pending state. All its fixtures rolled back.
- Applied/exported **`20261115130214_shieldrag_integrity_failure_audit`**. It adds one SECURITY INVOKER function with an empty fixed search path and service_role-only EXECUTE. Direct grant checks confirmed anon/authenticated cannot execute it and security_events RLS remains enabled. No table, policy, original migration, or ingestion route was recreated or weakened.
- Independent post-teardown checks returned **0 remaining ingestion Storage objects, 0 ingestion metadata rows, and 0 ingestion audit events**. Matching guarded account/document/chunk cleanup returned **remaining_fixture_rows = 0**. The private manifest was removed only after that confirmation; the ingestion journal was already removed after successful teardown.
- `pip check` passed. The latest Supabase Security Advisor returned **no findings**. One existing upstream AnyIO/Starlette test-client deprecation warning remains.

## Exact reproduction

Generate a fresh private fixture run and apply its setup using the authorized operator procedure in [testing.md](testing.md). From `backend/`, the successful command was:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_INGESTION = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = '.integration/task031-verified-20261115/manifest.json'
.venv/Scripts/python -m pytest -q -p no:cacheprovider --tb=short
```

That run has been cleaned up; use a new directory/manifest for reproduction. Ingestion teardown removes exact objects and audit rows, then the original guarded SQL removes the remaining fixture accounts/documents/chunks. Never commit generated files or credentials.

## Readiness and remaining limits

No local/cloud acceptance blocker remains. Changes stay on `feat/secure-document-ingestion` and update existing PR #2; merge remains manual after final code review and CI. Task 04 is not started.

Audit writes are separate committed transactions from the rejected approval. If both acknowledgements are lost, the event may already exist while the API returns 503; the UUID-only log supports investigation. Only internal retries share an event ID; separate HTTP attempts are separate observations. A persistent database outage cannot be made durably auditable by this request alone: it stays denied with 503 and an operational log, without a new retry queue or unrelated reconciliation feature. Existing upload partial-failure limits remain documented.

**Task 04 must independently revalidate stored SHA-256 immediately before text extraction, chunking or indexing.** Prior approval does not guarantee future Storage immutability. None of those features is implemented here.

## Historical Task 03 verification — 2026-11-15

## Current results

- Final complete suite: **138 passed, 0 skipped** in 42.59 seconds: 120 mocked/unit/orchestration tests and **18 real cloud integration tests**. All five new private Storage ingestion tests executed successfully.
- Actual FastAPI PDF/TXT uploads saved the exact original bytes in the private bucket with correct SHA-256, verified uploader identity, pending review state, and not_indexed status. Direct user-token and public-URL object reads were denied.
- Live API checks passed for metadata visibility, Student review denial, Admin approval/rejection, duplicate-transition conflicts, and tampering detection. A tampered object remained pending after approval was denied.
- Two simultaneous HTTP review attempts produced exactly one success and one conflict; audit reads confirmed one upload event and exactly one winning review event. Existing live Auth, trusted-role, PostgREST/RLS, restricted-content, pending/rejected chunk, and vector-RPC checks also passed.
- After ingestion teardown, independent live database counts confirmed **0 remaining ingestion Storage objects, 0 ingestion metadata rows, and 0 ingestion audit events** for the synthetic run. Guarded account/document/chunk cleanup returned **remaining_fixture_rows = 0**. Only then was the private password manifest removed; the ingestion journal was already removed by successful teardown.
- The prior Task 03 cleanup, interrupted by an automatic-review usage limit on November 14, was explicitly resumed on November 15 and independently returned **remaining_fixture_rows = 0**. The earlier cleanup claim was premature; the saved guarded SQL made safe recovery possible.
- Migration `20261114141719_shieldrag_secure_document_ingestion` is applied and exported. Existing tables, RLS, bucket configuration, original migrations, and non-fixture source data were preserved. Both write functions are SECURITY INVOKER, have a fixed empty search path, and deny EXECUTE to anon/authenticated while allowing service_role.
- Real operator-only `tests/ingestion_rollback.sql` passed for grants, actor roles, initial state, hash/state conflicts, approval/rejection, and audit counts; its fixtures rolled back. A separate database-only concurrent review check also produced one commit and one PT409 with a single review event, followed by exact scoped cleanup.
- `pip check` passed. The latest Supabase security advisor returned **no findings**. The previous November 14 Auth password-protection warning is historical; this task did not modify Auth settings.
- One existing upstream AnyIO/Starlette deprecation warning remains. No frontend, text extraction, chunking, embeddings, indexing, Gemini, generation, or AI Security Agent was added.

## Reproduction and environment resolution

The server key was configured in root `.env`, while the original loader only read `backend/.env`. Settings now resolve both files by absolute repository paths, independent of launch directory. Process environment variables win over backend settings, which win over root settings. The real key was not printed, copied, or committed; mocked test configurations explicitly avoid loading private dotenv files.

Generate fresh fixtures and follow [the ingestion procedure](document-ingestion.md) and [guarded fixture setup/cleanup](testing.md). From `backend/`, the successful full-suite command used:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_INGESTION = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = '.integration/task03-verified-20261115/manifest.json'
.venv/Scripts/python -m pytest -q -p no:cacheprovider --tb=short
```

That run's fixture credentials and rows have been removed. Reproduction requires a fresh run directory and setup, followed by Storage teardown and the matching guarded SQL cleanup.

## Remaining limits

There is no remaining live Storage credential or acceptance-test blocker. Storage and PostgreSQL still are not a distributed transaction: definite structured database failures trigger bounded compensation, while uncertain/lost responses preserve possibly committed objects and emit UUID-only reconciliation logs. Interrupted operations or failed cleanup can require operator work. Durable automatic orphan recovery and client idempotency keys are deferred.

PDF structural validation is not antivirus scanning or a full rendering guarantee; production resource isolation/rate limits require deployment controls. Test-only Auth provisioning is tied to the inspected managed schema. The native psql runner was unit-tested; real operator SQL ran through the connected Supabase tool. Auth revocation and audit retention follow platform behavior.

## Historical Task 03 progress — 2026-11-14

The earlier available run reported 133 passes and five explicitly skipped Storage tests because the root dotenv key was not being loaded. That result did not establish Storage acceptance. The November 15 full cloud run above supersedes that blocker and all five tests passed.

## Historical Task 02.1 verification — 2026-11-14

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
