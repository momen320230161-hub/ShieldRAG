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
