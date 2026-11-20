# Task 06.3 live verification

**NOT READY FOR MERGE.** One live pytest test ran and failed before any of the 14 RAG requests. The application revision was `f23273239743e634360919cb657b471ed8a54f43`. The pilot and reports are on `test/task063-live-verification`.

## Verified on the connected project

- Confirmed Supabase project identity, seven deployed migrations, a private `shieldrag-documents` bucket and zero eligible documents at preflight.
- Loaded Policy E revision `shield-security-calibration-5` at SHA-256 `fa68f0c166edf201a0a80412f53bb10ef5c863f05f6306d9d1e81d4e29c3887e`. Gemini returned HTTP 200 for the configured generation and embedding model metadata.
- Signed in as the two fresh synthetic users and verified the trusted Student and Admin profiles with signed JWTs. The Student credential retained the Student role despite a conflicting user metadata role, request header and query parameter. An invalid bearer token received HTTP 401.
- Verified role-scoped PostgREST reads and vector RPC results on six synthetic authorization fixtures. Both roles could read approved public chunks. The Admin could also read approved restricted chunks. Pending and rejected chunks were excluded for both roles.
- Verified that the deployed audit RPC execute grant is exclusive to `service_role` among the three application roles checked.

## Point of failure and cleanup

The pilot uploaded and approved its first synthetic TXT. The index endpoint raised `PermissionError` while starting the Windows extraction worker because opening its named pipe returned `WinError 5`. The run stopped before a Gemini embedding or generation call. No fixture TXT was indexed. The runner now records a sanitized indexing exception for this failure.

The scoped Storage and document teardown and synthetic session logout completed. The SQL operator then ran the matching guarded fixture cleanup. An independent read found zero test users, identities, sessions, profiles, documents, chunks, application audit rows and Storage objects. The private bucket and the recorded RLS policy and public table-grant fingerprints matched preflight. The private manifest and ownership journal remain under the ignored `backend/.integration/task063/` directory.

The pilot still needs all 14 requests. End-to-end role isolation, real citation provenance, per-request audit acknowledgement, duplicate-event handling, fail-closed audit behavior, answer quality and latency lack live measurements. The non-live suite covers the existing security and audit regressions. See the [comparison](../backend/security_evaluation/task063/live-comparison.md) and [sanitized report](../backend/security_evaluation/task063/live-report.json).

## Reproduction

Run from `backend/` with the locked dependencies installed in the active Python environment.

```powershell
python -m pytest -q -m "not integration" -p no:cacheprovider --basetemp .integration/task063-regression-check
python -m pip check
python -m pytest -q tests/test_rag.py::test_txt_pdf_page_provenance_and_worker -p no:cacheprovider
```

The first command passed 336 tests with 43 integration tests deselected and one existing AnyIO deprecation warning when run with working subprocess and temporary-directory permissions. `pip check` passed. The last command exercises the extraction worker without using an external service. Run it on the same host and with the same permissions planned for a future live run, before creating cloud fixtures.

For a separately authorized live run, confirm the expected project, empty fixture inventory, migration versions, private bucket, audit grants, configured Gemini models and Policy E digest. Use a fresh ignored directory. The operator must apply `setup.sql` to that verified project, then run the matching `cleanup.sql` even if pytest fails. See [the guarded fixture procedure](testing.md).

```powershell
python -m scripts.integration_fixtures --directory .integration/task063-review
$manifest = Get-Content .integration/task063-review/manifest.json -Raw | ConvertFrom-Json
$env:SHIELDRAG_FIXTURE_MANIFEST = (Resolve-Path .integration/task063-review/manifest.json).Path
$env:SHIELDRAG_TASK063 = $manifest.run_id
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_RAG = '1'
# Apply the matching guarded setup before invoking the pilot.
python -m pytest -q tests/pilot_task063.py -p no:cacheprovider --tb=line
# Always run the matching cleanup.sql as the authorized operator after pytest returns.
```

The pilot caps logical requests at eight indexing embeddings, fourteen query embeddings and fourteen generations, with up to 108 provider attempts. It alternates route order across the seven case pairs and uses a private start marker to prevent reruns with the same manifest. After teardown, independently query the run-owned resource IDs and compare the bucket, grants and policies with preflight. Keep fixture SQL, credentials and recovery journals out of Git.

## Task 06.3.1 worker readiness

**WORKER FIX VERIFIED — LIVE PILOT REQUIRES NEW AUTHORIZATION**

The offline diagnosis ran on Windows 11 build 26200 with locked CPython 3.12.10, from the checkout's `backend/` directory. The original focused test, before editing the application, reached CPython's `asyncio.windows_utils.pipe()`. The server end of the worker's stdin named pipe was created. Opening its peer via `_winapi.CreateFile` raised `PermissionError` with `WinError 5` before the extraction worker started.

| Execution context | Child process with standard streams set to `DEVNULL` | Real worker using private pipes |
| --- | --- | --- |
| Restricted Codex session | Exited 0 | Named-pipe open denied before child startup. The focused test now reports the bounded 503. |
| Same Windows host, authorized execution outside the session sandbox | Exited 0 | Synthetic TXT round-trip and exit 0. The original focused regression also passed with actual TXT and PDF extraction. |

Both probes used the same Python environment and working directory. The comparison isolates the failure to opening the named pipe in the restricted execution context. The tests did not identify a specific pipe ACL or endpoint-protection rule. The original restricted context retains the **ENVIRONMENT BLOCKER — EXTRACTION WORKER CANNOT START**. The same Windows host supports the worker in the verified execution context.

`backend/app/services/extraction.py` now maps an OS-level startup error to HTTP 503 with a fixed message. Tests in `backend/tests/test_rag.py` verify that simulated spawn and named-pipe denials fail the owned index job without calling embeddings or publishing chunks. `backend/tests/test_extraction_worker.py` uses real local subprocesses to check repeated and concurrent extraction, malformed and oversized input, process exit, timeout and crash cleanup, and no leftover files. The extraction worker keeps its private pipes, process isolation, and existing limits and integrity checks.

The focused Windows suite passed **9 tests**. The full offline suite passed **344 tests**, with **43 integration tests deselected** and one existing AnyIO deprecation warning. `pip check` passed. Explicit Task 06.3 collection found one test, and running it with the live opt-in unset skipped it. Linux runtime verification was unavailable locally. The code and tests use the existing platform-specific process flags and portable subprocess APIs. [Commands](testing.md#reproduce-task-0631-worker-readiness).

This task made zero Supabase fixture writes and zero Gemini calls. The [historical live report](../backend/security_evaluation/task063/live-report.json) retains the original failed run. For a separately approved pilot, first pass the real worker test using the same Python, working directory and shell permissions as the planned execution. Prepare two fresh synthetic accounts, eight TXT sources and a new recovery manifest. Keep the seven pairs and fourteen RAG requests within 36 logical Gemini operations and 108 attempts, and apply the guarded teardown and independent inventory check.
