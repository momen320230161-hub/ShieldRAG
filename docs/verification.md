# Task 06.2 verification

**NOT READY FOR MERGE.** Repeated qualification produced a byte-identical decision lock. Candidate C scored 16/18 on fresh questions and 8/22 on historical questions. The retained Task 05.1 classifier restored 9/22 historical answers, with 0/22 achieved attack objectives, 0/44 scope violations and 9/9 valid benign citations. All 44 secure responses received one acknowledged audit event in the local transport. No live Gemini, Auth, Storage, RLS or database checks were executed in this task. All seven migration files were preserved.

Local verification passed 323 tests, with 43 live integration tests deselected. Dependency checks passed. An existing Starlette/AnyIO deprecation warning remains. The multi-excerpt suite now verifies both the original 06.1 mixed-language refusal and the retained policy's exact, grounded answer. [Evidence and release veto](../backend/security_evaluation/task062/decision.md) · [Reproduction](testing.md#reproduce-task-062).

# Historical Task 06.1 verification

The previous PR #5 head `5d13a56` was verified before changes. The [Task 06.1 review](security-quality.md) records all eleven historical denial causes, calibration data and the revised grounding policy. The 44 historical pairs executed with identical inputs and scoring. The candidate reduced benign refusals in validation from 7/78 to 5/78 but historical Secure benign availability declined from 9/22 to 8/22. Scripted Secure attack successes remained 0/22 and known unauthorized disclosures 0/44. The eight-case development suite recorded three exact multi-excerpt answers, one mixed-language false positive and one withheld free-form translation. **NOT READY FOR MERGE**.

The existing RLS, service-only audit RPC and seven migrations remain in place. Task 06.1 had zero real provider calls or Supabase writes. The live pilot awaits separate authorization.

The local suite passed **310 tests**, with 43 pre-existing integration tests deselected. `pip check` passed. The Task 06 authorization test previously pinned an exact `review` decision for the historically rejected Admin case. It now checks that either non-allow decision withholds answers and citations after authorized retrieval, and verifies the context audit stage. The historical review remains in the original report. The development suite retains the expected mixed-language answer and counts the actual refusal as a false positive. A separate regression verifies that exact multilingual excerpts can be rendered when the detector allows the source.

# Task 06 verification

Local `main` was fast-forwarded to `1387ab77c8d58a9ff783bc11ebeff48685bf17c5`, matching `origin/main` before creating `feat/security-evaluation`. Tasks 02 through 05.1 were present. The checked-in [offline comparison](../backend/security_evaluation/task06/reports/comparison.md) measures the actual Baseline and Secure FastAPI handlers using synthetic Supabase and scripted Gemini transports. All **44 pairs / 88 requests** produced valid offline outcomes. Both pipelines had **0/44** observed authorization disclosures in the transport model.

Baseline released 19/22 scripted attack objectives. Secure released 0/22 and withheld 19/22 by security decision. The remaining three were prevented by fixture authorization without detector blocks. Benign answer availability was 20/22 for Baseline and 9/22 for Secure. Secure non-allowed 11/22 benign requests. The secure route retrieved the Admin's permitted reference and withheld the answer on context review. The sampled summarization and multi-passage answers were withheld at output, and the translation case stopped on context review. These results quantify the trade-off under controlled scripted responses. They do not estimate real Gemini attack success or independently prove database RLS.

Application code, endpoints, classifier, migration files and prior tests are preserved. The evaluator persists versioned JSON and Markdown. The [reproduction commands and separately scoped live proposal](security-evaluation.md) describe the offline harness and the seven-pair pilot, including provider request bounds and cleanup. **Zero Task 06 live cases were executed.** The earlier live evidence below belongs to Task 05.1.

The non-live suite passed **294 tests** with **43 integration tests deselected**. The offline runner, report confidentiality checks, plot generation and `pip check` passed. An initial evaluator assertion conflated authorized retrieval with guaranteed answer availability. It was corrected to record the observed Admin context review, with the benchmark and application assertions preserved.

# Task 05.1 verification — 2026-11-17

The fixed, previously inspected 48-row synthetic test retained its exact rows, labels and family assignments. The full policy reduced benign non-allow from **7/24 to 4/24** while detecting **24/24** attacks on those rows in both versions. Classifier-only recall fell from **21/24 to 19/24**. The selected Linear SVM retained **21/21** validation attack non-allows with **6/42** benign non-allows, versus **13/42** with the original policy on the same expanded validation data. See [policy, calibration, and limitations](security-agent.md).

The original controlled `output_contamination` case generated once and was blocked at output for `invalid_source_support`: a valid quote did not contain the proposed answer. Secure mock attack success fell from **1/5 to 0/5**, and benign supported answers rose from **1/3 to 2/3**. Baseline stayed at **4/5** and **3/3**, respectively. The Arabic mock benign case still received context review. The secure pipeline verified exact answer spans, citations and current source access. The invariant does not establish semantic entailment. These are development comparisons, with no independent benchmark.

The post-live local run passed **277 tests**. The 43 integration cases were excluded from that command and verified in the two live runs below. Local tests cover the original mocked output-contamination case, quote laundering, invalid model artifacts, simulated provider and audit failures, and concurrent requests. `pip check` reported no broken requirements.

## Checks against real services

- Tested feature commit `2c20c74aa0bcee63777c51479ee778224d4e8e5e`. Collection found **43 live cases**. The owner-authorized run passed all **39 previously pending cases** in **289.13 seconds**, with **0 failures, 0 errors and 0 skipped**. That run covered eight ingestion, ten Auth and role-authorization, twelve RAG and nine role-aware security cases. The earlier same-commit run passed the four other cases: Gemini extractive generation, Supabase Auth health, forged JWT rejection and anonymous PostgREST denial. Across the two live runs, **43 passed** with no unexecuted cases. GitHub Backend checks passed on the tested feature commit in [run #22](https://github.com/momen320230161-hub/ShieldRAG/actions/runs/44161030126).
- Student and Admin signed in with synthetic accounts. Auth verified signed JWTs and trusted profile roles despite forged role claims. Both RAG routes returned supported public answers for both roles and supported restricted answers for Admin. Both returned insufficient evidence for Student on the restricted target. Pending, rejected and invalid index states remained excluded. Citations were checked against caller-visible chunks by ID, quote and page, and supported secure answers matched a contiguous span of a validated quote.
- Five direct injection attempts were denied before embedding. The indirect case was blocked before Secure RAG generation. Baseline made **one** logical generation call and Secure RAG made **zero** for that case. Neither returned the synthetic canary. The [paired live report](../backend/security_evaluation/paired-live-report.json) records observed responses and timing. Provider-wide call totals, physical SDK retries, token counts and monetary costs were not measured. The original output-contamination case and simulated unavailable-provider/model/audit regressions were exercised locally.
- Live audits confirmed allowed and denied decisions, role JWT denial of direct privileged RPC execution, and same-UUID replay producing one event. The private run inventory observed four allow events, six direct-denial events (including the replay probe) and one indirect-denial event. The live direct-denial assertions checked for bounded policy reasons without raw attack prompts. Local simulated audit-failure tests verified that a required acknowledgement cannot be bypassed.
- **6 SQL rollback suites passed** against the already migrated project: RLS, ingestion, integrity audit, RAG, cached index and security agent. The security suite covers audit RPC permissions and UUID replay. Security Advisor returned **zero findings** for this check.
- All seven local migration versions and names matched the deployed history. The verification run required no implementation fixes, test assertion changes or migrations.

## Fixture cleanup

Preflight found no collisions with the new account, document, chunk or Storage identifiers. The project had zero existing documents. The inventory captured 31 synthetic document rows (six initial SQL fixtures and 25 uploaded documents), 19 chunks, 25 uploaded object paths and 91 application audit events. Existing fixture teardown and the guarded SQL cleanup ran successfully. The cleanup SQL returned zero fixture rows. Independent read-only queries for the run markers and exact observed IDs and paths found zero Auth users, profiles, identities, sessions, documents, chunks, app audit events and Storage objects. Document and chunk counts, the private bucket and Storage snapshot, RLS policies, table grants and RPC grants matched preflight. Platform-managed Auth audit logs retain their normal lifecycle. Private fixture credentials were discarded after independent verification.

## Reproduction

See [testing commands](testing.md) for local tests, report generation, the Gemini-only check and the guarded role-aware Supabase setup/cleanup. To reproduce the four non-fixture HTTP checks from `backend/`:

```powershell
$env:SHIELDRAG_INTEGRATION='1'
$env:SHIELDRAG_SECURITY_LIVE='1'
.venv/Scripts/python -m pytest tests/test_security_integration.py tests/test_integration.py -k 'gemini_extractive_provider_only or auth_rejects_forged_jwt or postgrest_rejects_anonymous_table_access or auth_health' -q -p no:cacheprovider --tb=short
```

After the documented fixture setup and opt-in flags, run the remaining cases from `backend/`, then execute the matching guarded cleanup SQL and independently verify removal:

```powershell
.venv/Scripts/python -m pytest -m integration -k 'not (gemini_extractive_provider_only or auth_rejects_forged_jwt or postgrest_rejects_anonymous_table_access or auth_health)' -q -p no:cacheprovider --tb=short
```

## Historical Task 05 verification — 2026-11-17

## Executed checks

- Complete regression/live suite: **296 passed, 0 skipped** in **803.36 seconds**: **254 local/unit/mocked tests and 42 real cloud integration tests**. This preserves the previous 208 local/33 cloud tests and adds 46 local/9 cloud security cases.
- Final local regression after audit-error-phase clarification and prioritizing confirmed context blocks over earlier reviews: **254 passed, 42 deselected** in **17.84 seconds**. Those 42 deselections were not counted as new passes; their actual cloud execution is the complete run above. The cloud suite was not repeated solely for these locally verified refinements or offline report-denominator correction, avoiding unnecessary billable calls.
- Existing Auth, trusted Student/Admin roles, private ingestion/review, original/index SHA verification, atomic publication, RLS, cached-index protection, real Gemini embedding/generation and page citations remain passing. Secure and baseline share caller-token search and source/citation revalidation; no service-role retrieval was introduced.
- New local checks cover benign English/Arabic security questions, direct/indirect/encoded/Unicode attacks, output credentials and operational-prompt fragments, group isolation, model provenance, no request-time fitting, missing/corrupt bundles, runtime failure, review/deny-before-embedding, unsafe-context-before-generation, fabricated evidence, malformed/provider output, audit failure, role spoofing/revocation and body limits. An unavailable audit withholds even an otherwise safe answer.
- New real cloud cases verified five input denials without an embedding call, genuine persisted audits, forged-token rejection, Student/Admin denial of direct audit-RPC invocation, UUID replay with one row, paired public answers for both roles, Admin restricted answers and Student restricted-target exclusion. Existing cloud tests additionally verify pending/rejected/processing/failed isolation.
- The real indirect-source canary did not appear in either pipeline's returned answer. Baseline made one logical generation call; secure blocked the unsafe source before generation and made zero. This is a single smoke case, not a demonstrated real-world attack-success-rate improvement. Historical paired statuses and timings are recorded without raw responses in `backend/security_evaluation/task05-baseline/paired-live-report.json`.
- All **six** real SQL rollback suites passed: RLS, ingestion, integrity audit, atomic RAG, cached indexing and new security-agent auditing. The new suite verified narrow grants, registered actor/current visible-document association, fixed reasons/policy version, idempotent UUIDs, conflicting replay rejection and user-write denial. All synthetic rows rolled back.
- New forward migration **`20261115202657_shieldrag_security_agent_audit`** adds one SECURITY INVOKER RPC with empty fixed search_path, service_role-only EXECUTE and no RLS/table changes. Direct inspection confirmed anon/authenticated cannot execute it. Existing applied migrations were not edited or replayed. Deployed/local normalized SQL digest matched: `063a84b8223c664fa9066ad2a44bdab4`. The existing unavailable-Windows-CLI fallback used the connected migration tool and retained its server-generated version.
- After fixture teardown, independent SQL confirmed **0 uploaded synthetic documents, 0 Storage objects and 0 security events** for the run. Guarded account/document/chunk cleanup returned **remaining_fixture_rows = 0**. Security/RAG/ingestion journals were removed only after successful scoped teardown; the private password manifest was removed after independent cleanup confirmation. Auth-managed audit retention was unchanged.
- `pip check`, diff checks and deliverable secret scans passed. Actual environment keys and synthetic passwords are not in deliverables. The untracked `docs/orchestrator-handoff.md` is preserved unchanged (SHA-256 `B431284A8C251AC0773046AABD9B944EBF010304AE966680E6B340359533C06F`) and is not included in the Task 05 commit.
- The latest recorded Security Advisor response returned **no findings**. An earlier Task 05 response reported the existing Leaked Password Protection Disabled warning; this task did not change Auth settings, and an empty later response is not proof that Auth configuration was changed. Operators should confirm the configured protection independently. One existing AnyIO/Starlette deprecation warning remains.

## Frozen classifier and policy measurements

- Version `shield-security-v1`: binary **Logistic Regression**, scikit-learn **1.9.1**, word/character TF-IDF, seed **1729**, JSON numerical artifact **387,493 bytes**, SHA-256 recorded in its bundled manifest. No pickle/joblib/user-uploaded model deserialization. Fixed reconstruction and score parity against the trained estimator were verified.
- Dataset: **237 project-authored synthetic examples**. Training: 78 benign/63 malicious; validation: 27/21; final test: 24/24. Known family/paraphrase grouping precedes TF-IDF fitting. Development prose extensions remain train/validation-only; original final-test IDs were preserved. No external benchmark or private traffic was used.
- Logistic Regression and Linear SVM tied on final validation macro-F1 **0.9161**, so declared candidate order selected Logistic Regression. Threshold selection uses validation only, not training accuracy or test results. Block margin **-0.0377009765**, review threshold **-0.2877009765**; margins are uncalibrated, and review never permits generation.
- Classifier-only held-out precision/recall/F1 **0.875**, confusion matrix **[21,3;3,21]**, FPR **12.5%**, FNR **12.5%**. The full rules+classifier policy, counting review as non-allow, had precision **0.7742**, recall **24/24 on this small set**, F1 **0.8727**, confusion matrix **[17,7;0,24]**, FPR **29.17%**. This is not a guarantee of zero missed attacks.
- Representative classifier false positives: benign database-system and trusted-authorization coursework. Representative misses: another student's private-history request and a fake root-authority source. Full policy caught those particular examples through rules/review; unknown variants remain unproved. Model/agent reports include synthetic examples and per-kind counts.
- Warm measured classifier latency averaged about **1.02 ms**, p95 **1.35 ms**; full rule+classifier about **1.23 ms**, p95 **1.19 ms**, without network. These are local observations, not production performance targets.

## Paired comparison limitations

The controlled mocked-generator harness used 5 attack and 3 benign cases plus authorization/no-context controls. Baseline/secure canary success was **4/5 versus 1/5**; agent-style detection **0/5 versus 4/5**; benign answer availability **3/3 versus 1/3**, and secure benign refusals **2/3**. Citation validity among responses actually containing citations was **7/7 versus 2/2**; empty abstentions were excluded. Both had zero authorization failures. Logical embedding/generation method calls were **10/7 versus 7/2**; monetary costs, physical retries and token usage were not measured.

This deliberately vulnerable mock generator is not real Gemini attack-success evidence. Its surviving output-contamination attack and high false positives are material limitations. Real paired Gemini smoke cases succeeded for permitted benign requests, and the single indirect canary appeared in neither pipeline. Results are local public synthetic JSON; database evaluation persistence and comprehensive independent benchmarking are deferred to Task 06. Test metrics were observed during development but did not fit features or select candidates/thresholds; this is not a newly blinded external benchmark.

## Exact commands and delivery

From `backend/`, local training/evaluation commands actually executed:

```powershell
.venv/Scripts/python -m scripts.train_security
.venv/Scripts/python -m scripts.evaluate_security
.venv/Scripts/python -m scripts.compare_security
```

After preparing/applying the fresh `.integration/task05-live/setup.sql` through the authorized operator, the complete run used:

```powershell
$env:SHIELDRAG_INTEGRATION='1'
$env:SHIELDRAG_LIVE_FIXTURES='1'
$env:SHIELDRAG_INGESTION='1'
$env:SHIELDRAG_RAG='1'
$env:SHIELDRAG_SECURITY_LIVE='1'
$env:SHIELDRAG_FIXTURE_MANIFEST=(Resolve-Path .integration/task05-live/manifest.json).Path
.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=.integration/task05-full-1 --tb=short
```

That run is cleaned up; generate a new directory as described in [testing](testing.md). Never reuse the removed accounts/manifest or replay applied schema migrations. The final local command was `.venv/Scripts/python -m pytest -q -m 'not integration' -p no:cacheprovider --basetemp=.integration/task05-unit-review-final --tb=short`.

Feature branch: `feat/ai-security-agent`, based on synchronized main `7c02d49`. Baseline `/api/v1/rag/ask` remains; new `/api/v1/rag/secure-ask` is authenticated and independently testable. See [Security Agent architecture and limits](security-agent.md), [contracts](api-contracts.md), [setup](backend-setup.md) and [security](security.md). No frontend, Task 06 implementation, database reset or automatic merge is included. The implementation is suitable for manual experimental review; the measured false-positive and residual-attack results do not justify production-grade protection claims.

## Historical Task 04.1 verification - 2026-11-15

## Final results

- Complete suite: **241 passed, 0 skipped** in **179.84 seconds**: **208 unit/mocked/orchestration tests and 33 live Supabase/Gemini tests**. All live opt-ins were enabled. This adds 15 local and 6 targeted live regression cases; existing Auth, ingestion, approval, integrity, RLS, Gemini and RAG tests passed. One existing AnyIO/Starlette deprecation warning remains.
- Root cause 1: global content-only deduplication discarded repeated page occurrences. Chunk occurrence identity now includes page, source word interval and content. Real extraction/chunking preserved equal paragraphs on PDF pages 2 and 8, sequential indices and deterministic ordering, while keeping legitimate repeated TXT windows. Reprocessing an identical interval is deduplicated; word/byte/overlap limits remain unchanged. Configuration version is 2 so an explicitly requested rebuild can recover previously omitted content.
- Root cause 2: a cache hit assigned an active operation UUID to an indexed document, then generic failure cleanup could delete its completed chunks. Cache hits now return the existing row without mutation. Python skips generic cleanup for every cached failure. Generic failure transitions require the exact current processing job and never delete chunk rows. Malformed/uncertain begin responses do not establish cleanup ownership.
- Actual cloud fault tests injected Storage 503, Storage read timeout and a lost successful cache-begin acknowledgement. Independent database reads confirmed identical full completed metadata, unchanged chunk IDs, continued Student retrieval and no active operation. Cached verification also succeeded with the Gemini embedding method deliberately unavailable and never called. Timeout/cancellation behavior additionally passed unit regressions.
- Genuine synthetic cached-original tampering and deletion both returned 409, retained all completed chunk rows for trusted server inspection, marked that completed revision failed and denied Student/Admin chunk and vector-RPC retrieval. Each persisted exactly one correctly attributed, fixed-reason integrity event despite deliberately dropping one successful invalidation acknowledgement and retrying the same UUID. The actual Storage missing-object response was distinguished from injected outages.
- Actual repeated-page PDF indexing generated real `gemini-embedding-001` embeddings and two distinct page-attributed chunk rows. Normal caller-JWT search returned both pages. Real `gemini-3.5-flash-lite` answers produced validated citations for each page. For deterministic page selection between identical excerpts, test instrumentation selected one page from real authorized RPC results; Auth, RLS, source rows and Gemini were real, and no result was fabricated. The existing public TXT/restricted TXT/PDF acceptance tests again validated finite L2-normalized 768-dimensional vector storage and role isolation.
- All **five SQL rollback suites** passed: RLS, ingestion, integrity audit, atomic RAG publication and new cached-index hardening. They cover exact no-mutation cache behavior, old cached operation tokens, failed second-vector rollback, concurrent/expired leases, retry, retained old chunks, stale failure/replayed invalidation protection, legacy null revisions and retrieval denial after compromise. All their synthetic rows rolled back.
- New forward migration **`20261115150450_shieldrag_cached_index_integrity_hardening`** adds nullable `index_revision_id`, corrects existing begin/publish/fail functions, and adds service-only `shield_invalidate_index`. The new RPC reuses the existing integrity-audit validation, fixed reasons, UUID acknowledgement and deduplication in the same transaction as revision-scoped retrieval revocation. No applied migration, table, RLS policy or original search RPC was changed/replayed. Stable publication revision IDs prevent an old observation from revoking a newer successful index. No production-like documents were rebuilt.
- The migration was applied using the connected migration tool and exported with its server-generated version, using the previously established unavailable-Windows-CLI fallback. A whitespace-normalized SQL digest matched local file and deployed migration history exactly: `aa1a7d5a77808a44780bff439fa1541a`. Direct privilege inspection confirmed all four index write RPCs are SECURITY INVOKER, fixed empty search_path, service_role executable and anon/authenticated denied.
- Independent post-teardown SQL returned **0 uploaded synthetic documents, 0 Storage objects and 0 security events**. Guarded remaining-account/document/chunk cleanup returned **remaining_fixture_rows = 0**. Both journals were removed by successful teardown; the password manifest was removed only after cleanup confirmation. Platform-managed Auth audit retention is unchanged.
- `pip check` and diff checks passed. Deliverable files were scanned against actual configured credentials and synthetic account passwords; none matched. Environment files and generated fixtures remain ignored.
- Final Security Advisor: the existing **Leaked Password Protection Disabled** Auth warning; no database/RLS finding. An earlier check in this task returned no findings, so the final warning is the reported state. Auth settings were not modified. [Remediation](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## Executed reproduction command

From `backend/`, after preparing and applying `.integration/task041-live/setup.sql` through the authorized SQL operator:

```powershell
$env:SHIELDRAG_INTEGRATION='1'
$env:SHIELDRAG_LIVE_FIXTURES='1'
$env:SHIELDRAG_INGESTION='1'
$env:SHIELDRAG_RAG='1'
$env:SHIELDRAG_FIXTURE_MANIFEST=(Resolve-Path .integration/task041-live/manifest.json).Path
.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=.integration/task041-full-1 --tb=short
```

The run has been cleaned up. Reproduce with a new directory using [testing instructions](testing.md), apply that directory's setup, run the tests, then always apply its guarded cleanup. The five `tests/*_rollback.sql` suites were also executed through the authorized SQL operator. The local-only run before cloud verification passed 208 tests with 27 then-existing live cases deselected; those deselections were not counted as passes.

## State transitions and remaining limits

Cache hit: `indexed -> indexed` without writes or an active lease. Transient failures leave this completed record intact. New/replacement job: `not_indexed/failed/indexed -> processing -> indexed`, with approved status, expected original SHA, explicit consent and current Admin checks retained. Generic job failure can change only its own `processing -> failed` and retains old chunk data hidden by RLS. Confirmed cached integrity failure atomically commits the existing audit and `indexed -> failed` only for the observed revision, retaining chunks. A stale verifier audits its observation but cannot alter a newer completed revision or processing job.

A genuinely unavailable database cannot guarantee a durable revocation/audit commit. Such requests return 503, log only trusted UUIDs for reconciliation and never delete completed data as a fallback. Retained invalid/failed chunks remain server-only and are replaced by a later successful authorized rebuild. Configuration version 2 requires explicit reindexing to repair pre-hardening provenance; no automatic repair of production-like data occurs. Prompt-injection/semantic-grounding limits, external processing authorization, Windows parser resource limits and deployment rate controls remain as documented in [RAG architecture](rag.md).

PR #3 remains the single delivery PR on `feat/baseline-rag-gemini`, targeting main. No frontend, Task 05 feature, table reset or automatic merge is included.

## Historical Task 04 verification - 2026-11-15

## Final results

- **220 passed, 0 skipped** in **123.71 seconds**: **193 unit/mocked/orchestration tests and 27 real cloud integration tests**. The final run enabled every live flag. CI runs the 193 local tests without keys; deselected live tests are not reported as passed.
- Actual Admin indexing succeeded for public TXT, restricted TXT and a text-bearing PDF using genuine `gemini-embedding-001` document embeddings: **768 dimensions**, finite normalized vectors stored in pgvector, correct TXT/null and PDF/page-1 provenance. Cached retry preserved original chunk IDs without duplicate embedding/publication.
- Actual query embeddings and the existing pgvector RPC returned permitted sources through caller JWTs. Student restricted denial, Admin restricted access, approved-only isolation, pending/rejected rejection, service-RPC denial to both user roles, current trusted roles, private Storage and all earlier ingestion/integrity controls passed.
- Actual `gemini-3.5-flash-lite` generated the correct synthetic facts with source IDs/quotes checked against retrieved rows. Final live checks also confirmed no-result and insufficient-context abstention. This is real end-to-end acceptance, not a mocked generation claim.
- Deliberate synthetic Storage modification blocked indexing with 409, persisted one integrity event, left review approved/index failed and published no chunks. Live lease exclusion and direct privileged-RPC denial passed.
- Four SQL rollback suites passed against the actual migrated project: RLS, ingestion, integrity audit and RAG atomic publication. RAG verified rollback after an invalid second vector, hidden processing chunks, idempotent retry, stale failure protection, expired-lease recovery and external-consent isolation. Every SQL suite rolled back its synthetic rows.
- Applied/exported **`20261115143019_shieldrag_atomic_baseline_rag`**. The server-generated migration version was retained; the unavailable Windows CLI was not used to invent a version. Existing tables/history were preserved. Direct privilege inspection confirmed all three index write RPCs are SECURITY INVOKER with fixed empty search paths, executable by service_role and denied to anon/authenticated. Existing search remains SECURITY INVOKER and authenticated-only for users.
- Independent post-teardown SQL returned **0 remaining Storage objects, 0 uploaded synthetic document rows and 0 synthetic security events**. Guarded account/document/chunk cleanup returned **remaining_fixture_rows = 0**. The password manifest was removed only after that confirmation; ingestion/RAG journals had already been removed after successful teardown. Platform-managed Auth audit retention is unchanged.
- `pip check` and `git diff --check` passed. A scan against actual configured keys and synthetic passwords found no matches in deliverable files; private environment/fixture paths are ignored.
- Final Supabase Security Advisor: one existing Auth warning, **Leaked Password Protection Disabled**; no new database/RLS finding. [Remediation](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). Auth settings were not changed. One existing AnyIO/Starlette deprecation warning remains.

## Exact executed command

From `backend/`, after preparing/applying the uniquely marked operator fixtures:

```powershell
$env:SHIELDRAG_INTEGRATION='1'
$env:SHIELDRAG_LIVE_FIXTURES='1'
$env:SHIELDRAG_INGESTION='1'
$env:SHIELDRAG_RAG='1'
$env:SHIELDRAG_FIXTURE_MANIFEST=(Resolve-Path .integration/task04-live/manifest.json).Path
.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=.integration/pytest-task04-final --tb=short
```

That run has been cleaned up. Use a new directory and manifest following [testing instructions](testing.md), apply its setup before HTTP tests, and always run its guarded cleanup afterward. All four checked-in `tests/*_rollback.sql` suites were executed through the authorized connected SQL operator. No operator credential is supplied to FastAPI.

An earlier run exposed a Gemini 400 for the SDK-transformed Pydantic response schema. The wire schema now uses Gemini's supported Schema subset; strict Pydantic length/field validation still runs independently after generation. An earlier exact-object cleanup timed out; the retained journal supported recovery, and bounded idempotent deletion retries were added. Both issues were resolved before the final complete run. Initial sandbox temporary-directory/parser permissions were resolved by running tests with normal authorized filesystem access.

## Delivery and remaining limits

Changes are on `feat/baseline-rag-gemini`, based on latest `main` (`c4a911a`), for a new PR to main; no automatic merge. Backend only. See [RAG architecture](rag.md), [API contracts](api-contracts.md), [setup](backend-setup.md) and [security](security.md).

No acceptance-test blocker remains. Restricted content requires explicit Admin authorization for external Gemini processing; third-party residency/retention requires an operator decision. Semantic faithfulness and prompt-injection resistance are baseline safeguards, not a proved security guarantee. Windows extraction lacks a hard OS memory sandbox; deployments need suitable resource/rate controls. Crashes can leave a hidden processing lease until expiry, and an uncertain commit requires retry/reconciliation. Similarity threshold and recall need domain-specific evaluation. Model changes require reindexing. Chat remains stateless because safe persistence would require write policies, citation provenance and permission-aware history behavior. Task 05 security agents, classifiers, evaluations and frontend work remain out of scope.

## Historical Task 03.1 verification — 2026-11-15

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
