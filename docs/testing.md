# Testing and live verification

The current offline release check covers both FastAPI routes, read-only output claims, comparative answer availability and the complete English and Arabic XQuAD editions. Source data stay in an ignored directory. [Reproduction commands and the separately authorized live proposal](../backend/security_evaluation/output-calibration/decision.md#reproduction).

## Reproduce Task 06.2

From `backend` with the locked Python 3.12 environment, reproduce qualification in an ignored directory, compare selection-file hashes, then replay both the locked experiment and the retained release policy. The checked-in selection SHA-256 is `cd78c6cc29a4d5b428aae0d70482cd400755fa0514fbf87bda56de1753007ff0` on the documented environment. Timing may vary. All provider transports in these commands are local fixtures.

~~~powershell
.venv/Scripts/python -m scripts.qualify_security --output-dir .integration/task062-reproduction
Get-FileHash .integration/task062-reproduction/selection.json, security_evaluation/task062/selection.json
.venv/Scripts/python -m scripts.replay_quality --output-dir .integration/task062-candidate
.venv/Scripts/python -m scripts.replay_quality --retained --output-dir .integration/task062-runtime
.venv/Scripts/python -m pytest tests/test_quality_release.py tests/test_secure_quality.py tests/test_security_agent.py tests/test_evaluation_task06.py -m 'not integration' -q -p no:cacheprovider
.venv/Scripts/python -m pytest -m 'not integration' -q -p no:cacheprovider
.venv/Scripts/python -m pip check
~~~

Task 06.2 executed zero live cases. Reproduce the 06.1 implementation and its commands at commit `8ac119f`. On the current branch the legacy trainer writes a separate 06.1 bundle under a printed temporary directory. The legacy evaluator writes a report for the active runtime to its own temporary directory. [Release decision and limitations](../backend/security_evaluation/task062/decision.md).

The Task 06 [offline evaluation](security-evaluation.md) runs both RAG endpoints against isolated synthetic transports and produces paired reports. Its separate live pilot requires Task 06 authorization.

All commands run from `backend/` using Python 3.12. Mocked tests require no credentials:

```powershell
.venv/Scripts/python -m pip install -r requirements.lock
.venv/Scripts/python -m pytest -q -m 'not integration' -p no:cacheprovider
```

The unit suite preserves the original checks and adds error classification, malformed upstream JSON, and runner cleanup/failure tests. Live tests are opt-in; skipped tests are not passed tests.

## Basic live probes, without accounts

Configure `.env` from `.env.example`, then:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
.venv/Scripts/python -m pytest -q -m integration -p no:cacheprovider
```

Three probes check Auth health, anonymous PostgREST table-access denial, and invalid JWT rejection through FastAPI. Fixture-dependent ingestion/RAG tests skip unless their respective flags are enabled. Positive HTTP authentication is established only by the full workflow below. The earlier token-only smoke tests have been replaced by password sign-in and exact fixture assertions.

## Full live workflow

This requires an authorized operator SQL connection to the **same configured project**, plus the publishable key. FastAPI never receives the operator credential. No secret/service-role API key is needed. Setup creates two unique synthetic accounts, six documents, and six 768-dimensional chunks. It assigns Student/Admin roles in trusted profiles. Both accounts deliberately have misleading `user_metadata.role=admin` to test role trust.

The preceding key statement applies to the Auth/RLS suite. Full ingestion and Task 04 RAG acceptance additionally require a private modern server key; RAG requires the configured Gemini key and explicit external-processing/cost opt-in below. Seeded chunk fixtures now include verified indexed/hash/consent metadata. Pending/rejected fixtures deliberately retain chunks and indexed markers, so negative tests prove approval isolation rather than relying on absent content.

Install the test-only password-hashing dependency:

```powershell
.venv/Scripts/python -m pip install -r requirements-integration.txt
```

If PostgreSQL `psql` is installed, configure its standard `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, and `PGSSLMODE=verify-full` environment variables (or an equivalent private `PGSERVICE` configuration). Obtain connection settings and CA configuration from the project dashboard. Do not put credentials in shell command arguments. Then run:

```powershell
.venv/Scripts/python -m scripts.verify_live --directory .integration/run-001
```

Use a fresh directory under `.integration/` for each run. The runner prepares files, applies setup, executes **all tests**, and always attempts guarded cleanup in `finally`, including when setup or pytest fails. SQL and cleanup failures exit nonzero. It preserves the private manifest when cleanup fails and erases the password manifest after successful cleanup.

Without `psql`, use the same files through an authorized SQL operator, including the connected Supabase SQL tool:

```powershell
.venv/Scripts/python -m scripts.integration_fixtures --directory .integration/run-001
# Apply .integration/run-001/setup.sql to the configured project using the SQL operator.
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = '.integration/run-001/manifest.json'
.venv/Scripts/python -m pytest -q -p no:cacheprovider
# ALWAYS apply .integration/run-001/cleanup.sql, even if pytest fails.
# Confirm remaining_fixture_rows = 0, then remove only that manifest locally:
Remove-Item -LiteralPath '.integration/run-001/manifest.json'
```

Full mode fails if its manifest is missing or points to another project. It signs in through the real Supabase password endpoint, holds JWTs only in memory, and logs out those synthetic sessions at teardown. Assertions check successful JWT authentication through FastAPI, trusted profiles, approved public/restricted access, exact chunk/RPC result sets, pending/rejected exclusion, a tampered signed JWT, and a denied Student role update verified independently as Admin. Positive assertions prevent empty RLS/RPC results from passing silently.

Setup writes are test-only SQL transactions. They must commit before separate HTTP requests can see the fixtures, so cleanup is a second guarded transaction rather than a rollback of setup. Cleanup verifies account markers, document paths, and unexpected references before deleting exact fixture IDs; it aborts if unexpected data or remaining fixture rows are found. Keep the manifest and cleanup file until removal is confirmed. A crash or terminated process can require manual cleanup. If the guard refuses cleanup, investigate references rather than broadening deletion predicates.

The SQL account adapter writes the **inspected project's managed Auth schema** directly to create confirmed accounts without sending emails. It is test tooling, not a production signup path or general Supabase schema contract. Re-inspect Auth columns when upgrading Supabase; ordinary account provisioning should use the supported Auth Admin API. Generated SQL contains bcrypt hashes; the manifest contains passwords. Both live under ignored `.integration/`; protect them as credentials. Never use pytest `--showlocals`, HTTP wire logging, or upload these files as CI artifacts.

The older `tests/rls_rollback.sql` remains available for operator-only transactional assertions. It creates synthetic fixtures, tests Student/Admin RLS plus security-event ownership and denied approval writes, and rolls back everything. This check simulates database identities and complements actual password/JWT tests.

## Scope and results

See [verification results](verification.md) for observed passes, skips, cleanup, and limitations. `/health` is liveness only. Default CI runs only mocked tests; cloud integration is operator-run to keep privileged credentials out of pull-request workflows.

Task 03/03.1 has eight separately gated real private-Storage/ingestion tests. Set `SHIELDRAG_INGESTION=1` and configure a modern `SUPABASE_SECRET_KEY` before running the full workflow. Otherwise these tests explicitly skip; their absence must not be reported as successful Storage integration. Ingestion teardown deletes exact synthetic objects through the Storage API and their related audit/metadata rows before the existing account cleanup runs. Follow the [ingestion procedure](document-ingestion.md) and retain the ignored ingestion journal if cleanup fails.

Task 03.1 unit tests cover exact fixed event fields, pending-state preservation, Student denial, caller-controlled field rejection, lost/malformed audit acknowledgements, bounded retries, fail-closed 503s, and confirmed-versus-unconfirmed Storage failures. Separate HTTP attempts are tested as distinct observations; an internal retry must reuse one event UUID.

Live tampering now verifies the real persisted reviewer/document/type/decision/reason fields. Additional live cases verify missing-object auditing, server RPC replay without duplicate rows, denial of direct Student/Admin event inserts/updates, and rejection of an event ID rebound to another document. The lost-acknowledgement test uses real Supabase HTTP and database writes, then a controlled transport fault drops one successful response after commit. It verifies two backend write attempts with the same UUID and exactly one real event; this is explicitly a fault-injected cloud test, not a mocked database result.

Operator-only `tests/ingestion_rollback.sql` and `tests/integrity_audit_rollback.sql` separately check permissions, actor/document associations, fixed reasons, hash/state checks, event primary-key deduplication and user-write denial. All their rows roll back. Task 04 now adds independent original-byte verification and RAG acceptance as described below.


## Task 04 full RAG acceptance

Use a fresh ignored directory and the existing operator setup/cleanup workflow. The exact complete-suite command, from `backend/`, is:

```powershell
.venv/Scripts/python -m scripts.integration_fixtures --directory .integration/task04-run-001
# Authorized SQL operator applies this directory's setup.sql to the configured project.
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_INGESTION = '1'
$env:SHIELDRAG_RAG = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = (Resolve-Path .integration/task04-run-001/manifest.json).Path
.venv/Scripts/python -m pytest -q -p no:cacheprovider --tb=short
# ALWAYS apply this directory's cleanup.sql after pytest fixture teardown.
# Confirm remaining_fixture_rows=0 and no ingestion/RAG journal remains.
Remove-Item -LiteralPath '.integration/task04-run-001/manifest.json'
```

`SHIELDRAG_RAG=1` authorizes sending only synthetic fixture text/questions to Gemini and paying the small API cost. The suite uploads three approved synthetic sources (public TXT, restricted TXT, public text-bearing PDF), genuinely embeds and stores 768-dimensional vectors, checks normalization/page provenance, direct RPC/RLS and FastAPI search, validates generated answers/quotes/citations, and verifies no-result and insufficient-context abstention. Separate synthetic files test integrity denial and lease exclusion. No production-like document is processed.

Unit/mock checks cover deterministic overlap/deduplication/bounds, extraction, normalized vectors, provider retries/errors, original SHA verification before extraction and publication, cached/concurrent/partial indexing, roles, model/hash/consent filtering, revoked roles, untrusted prompt separation, missing/forged citations and credential rejection. CI runs these without cloud keys. Running the default suite without opt-in will skip live tests; report those as skipped.

For database transaction checks, the authorized SQL operator runs each checked-in file against the already migrated project: `tests/rls_rollback.sql`, `tests/ingestion_rollback.sql`, `tests/integrity_audit_rollback.sql`, `tests/rag_rollback.sql`, and `tests/cached_index_rollback.sql`. Each rolls back its synthetic rows. RAG checks failed second-chunk rollback, processing isolation, cached no-duplicate publication, expired-lease recovery, stale job denial and consent isolation. Cached-index SQL additionally verifies an unchanged complete document record on cache hits, legacy cache-token safety, retained chunk IDs after invalidation, Student/Admin retrieval denial, atomic audit retry deduplication, stale revision protection and safe retry after a failed rebuild.

The RAG fixture writes `rag-journal.json` before uploads. Teardown verifies synthetic owners, filename markers and canonical object keys, deletes only those exact Storage objects (bounded idempotent retries), then their chunks/events/document rows. The original account cleanup refuses unexpected references, so a failed teardown prevents account removal. Preserve the manifest and journal on failure; re-run the guarded teardown or an operator-reviewed recovery restricted to those exact run IDs. Never broaden deletion to other data or erase the manifest before confirming cleanup. Platform-managed Auth audit records remain subject to platform retention.

If local sandbox filesystem permissions prevent pytest temporary fixtures or subprocess execution, run the same command with normal authorized filesystem access. An optional fresh `--basetemp=.integration/pytest-run-001` keeps temporary fixtures under the ignored workspace. Do not reuse a directory containing retained recovery evidence.

## Task 04.1 hardening regressions

The same full-suite flags above run all Task 04.1 checks; use a fresh directory such as `.integration/task041-run-001` for setup, manifest and cleanup. To run just local RAG regressions, use `.venv/Scripts/python -m pytest tests/test_rag.py -q -p no:cacheprovider`. For just live RAG checks after operator fixture setup and all live flags, use `.venv/Scripts/python -m pytest tests/test_rag_integration.py -q -p no:cacheprovider --tb=short`.

New unit cases retain equal PDF paragraphs on pages 2/8 and repeated TXT windows, deduplicate only reprocessed source intervals, and validate either page's citation. Cached verification tests cover success without re-embedding, transient Storage errors, timeout/cancellation, Gemini outage, missing/invalid originals, hash mismatch, repeated audit acknowledgements and uncertain begin responses without destructive cleanup.

The six targeted live cases use real Supabase Auth, PostgREST, Storage, RLS and Gemini. Three deliberately inject a Storage 503, Storage read timeout or lost successful cache-begin acknowledgement; independent server/user reads verify unchanged completed metadata and chunk IDs, followed by successful cached verification with Gemini made unavailable. Two genuinely tamper with/delete an indexed synthetic original, drop one successful invalidation acknowledgement, then verify one real audit event, retained server-side chunks and denied Student/Admin chunk/RPC retrieval. These are explicitly fault-injected cloud tests, not real provider-outage claims.

The final live case indexes a synthetic eight-page PDF with identical text on pages 2/8 using genuine normalized embeddings, verifies both page-specific search results, and checks real Gemini-generated citations for each. To make citation selection deterministic between equal excerpts, its transport selects a single page from actual caller-JWT-authorized RPC rows. It does not fabricate a database result or bypass RLS; the selection is controlled test instrumentation. Normal production retrieval remains unchanged. Identical source text shares an embedding request while retaining distinct chunk rows and page provenance.

The configuration hash is version 2, so pre-hardening indexes need a separately authorized rebuild to recover previously omitted occurrences. Tests use newly indexed synthetic documents. No production-like data is rebuilt or repaired by this test workflow.

## Task 05 Security Agent and comparisons

Local tests require no real credentials or API calls:

```powershell
.venv/Scripts/python -m pytest tests/test_security_agent.py -q -p no:cacheprovider
.venv/Scripts/python -m scripts.train_security
.venv/Scripts/python -m scripts.evaluate_security
.venv/Scripts/python -m scripts.compare_security
```

Training explicitly writes the trusted local JSON bundle and public synthetic reports. CI loads the committed bundle. Review changed hashes and metrics after retraining. [Security Agent documentation](security-agent.md) explains grouped partitions, validation-only candidate and threshold selection, the reviewed fixed test and availability limits. Current `classifier-report.json`, `agent-report.json`, `split-manifest.json` and `paired-mocked-report.json` are under `security_evaluation/`. The original Task 05 reports are in `security_evaluation/task05-baseline/`. The mock generator intentionally emits synthetic contamination to exercise response screening.

Full real verification uses a fresh guarded fixture directory and an authorized SQL operator. Install `requirements-integration.txt` for fixture password hashing as described above. From `backend/`:

```powershell
.venv/Scripts/python -m scripts.integration_fixtures --directory .integration/task05-run-001
# Authorized SQL operator applies this directory's setup.sql.
$env:SHIELDRAG_INTEGRATION='1'
$env:SHIELDRAG_LIVE_FIXTURES='1'
$env:SHIELDRAG_INGESTION='1'
$env:SHIELDRAG_RAG='1'
$env:SHIELDRAG_SECURITY_LIVE='1'
$env:SHIELDRAG_FIXTURE_MANIFEST=(Resolve-Path .integration/task05-run-001/manifest.json).Path
.venv/Scripts/python -m pytest -q -p no:cacheprovider --tb=short
# ALWAYS run the matching cleanup.sql after fixture teardown; verify zero remains.
# Remove the password manifest only after confirmed cleanup.
```

`SHIELDRAG_RAG=1` and `SHIELDRAG_SECURITY_LIVE=1` explicitly opt into a small synthetic Gemini cost. Without these flags, the corresponding cases skip. `tests/test_security_integration.py` contains nine role-aware Supabase/Gemini tests and one Gemini-only test. The role-aware cases exercise real audit writes/role denial/replay, five direct denials before embeddings, paired safe public/restricted answers, exact quotes and pages from permitted chunks, the secure answer span and a real indirect-source case. A run with these fixtures writes a sanitized `paired-live-report.json` with statuses, citation presence, role isolation, canary outcome and timing.

To run only the real extractive provider check, with one logical Gemini request and no Supabase fixture or writes:

```powershell
$env:SHIELDRAG_SECURITY_LIVE='1'
.venv/Scripts/python -m pytest tests/test_security_integration.py -k gemini_extractive_provider_only -q -p no:cacheprovider --tb=short
```

The new security fixture records an ignored recovery journal, verifies synthetic ownership/allowed event categories, removes its exact new security-event IDs, then delegates object/chunk/document cleanup to the existing guarded RAG fixture. The original account cleanup refuses unexpected references. Preserve journals and manifests on failure. Platform Auth audit retention remains unchanged.

Run `tests/security_agent_rollback.sql` through the authorized operator in addition to the five existing rollback suites. It checks service-only EXECUTE, trusted actor/visible-document association, stable bounded reasons, event UUID deduplication, conflict rejection and unchanged user-write restrictions. Every row rolls back. No existing migration should be replayed against this project.
