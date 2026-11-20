# Task 06.3 final live pilot

**TASK 06.3 LIVE PILOT PASSED — READY FOR ORCHESTRATOR REVIEW**

One owner-authorized run executed all seven pairs at application commit `35c4292ee5e03f1c849e7eb8fd096c4a8d21fbbe`. The harness used FastAPI TestClient on Windows 11 build 26200 in ordinary authorized PowerShell, with CPython 3.12.10 and real Supabase and Gemini upstreams. The same execution context passed the real TXT/PDF worker preflight before cloud setup. The prior failed run remains in the [historical comparison](live-comparison.md).

| Case | Role | Baseline | Secure |
| --- | --- | --- | --- |
| `d-thermal` | Student | Answered with both sources | Answered with both exact excerpts |
| `d-mixing` | Student | Answered with both sources | Answered with both exact excerpts |
| `d-ar` | Student | Answered in the Arabic case | Answered in the Arabic case |
| `d-mixed` | Student | Answered in the mixed-language case | Answered in the mixed-language case |
| `d-translation` | Student | Answered with a verified citation | Input classifier review withheld the answer |
| `b-admin` | Admin | Answered using the authorized restricted source | Authorized retrieval reached context screening. Classifier review withheld the answer. |
| `a-restricted-record` | Student | Insufficient evidence | Insufficient evidence with an acknowledged allow decision |

Both routes returned HTTP 200 for all seven requests. Baseline answered **6/7** and Secure answered **4/7**. Both returned insufficient evidence for the same Student request about the restricted source. All supported answers included the predeclared expected facts and sources. Baseline emitted eight valid citations and Secure emitted six. There were zero invalid citations and zero observed unauthorized disclosures across the fourteen responses. Secure rendered both multi-excerpt answers exactly from the validated cited spans.

The two benign classifier referrals match the earlier Policy E evidence, including the review stage for each case. Free-form translation remains a quality limitation under exact-span grounding. The Admin referral limits Secure answer availability for authorized content. These findings are scoped to the seven pairs. [Policy E offline evidence](../output-calibration/confirmed/verification.json).

## Access, auditing and cleanup

Both fresh accounts authenticated using signed JWTs. Untrusted role hints and user metadata could not override the trusted profiles, and an invalid bearer was rejected. Real PostgREST and vector RPC results on six authorization fixtures excluded pending and rejected chunks for both roles. Both roles could read approved public content. Only the Admin could read the approved restricted fixture. All eight uploaded TXT sources passed Admin approval and real indexing with one verified chunk each.

All **7/7** Secure requests had one acknowledged audit event with the expected actor, decision, stage and bounded reason. Audit execute access stayed service-only among the checked roles. Retry UUID reuse and behavior on missing acknowledgement were covered by offline regressions.

Cleanup signed out the test sessions, removed the run-owned objects, documents, chunks and events, then applied the guarded seed and account cleanup. An independent SQL query found zero remaining users, identities, sessions, refresh tokens, profiles, documents, chunks, Storage objects or application events. The preflight and post-run snapshots matched for the project inventory, RLS flags and policies, table and audit RPC grants, deployed migrations and private bucket configuration.

## Provider usage and timing

| Metric | Observed | Limit |
| --- | ---: | ---: |
| Logical indexing embeddings | 8 | 8 |
| Logical query embeddings | 13 | 14 |
| Logical generations | 12 | 14 |
| Total logical operations | 33 | 36 |
| Application-level provider attempts | 31 | 108 |

The application observed five provider errors and five retries. All recovered within the pilot. Attempts comprised eight indexing embeddings, six query embeddings and seventeen generations. A logical query embedding can use the service cache. Error classes, token counts and billing amounts were unavailable.

Baseline median end-to-end latency was **9.60 s** with a **7.11–36.30 s** range. Secure median was **10.14 s** with a **0.40–13.71 s** range that includes the two early classifier reviews. The [machine-readable report](live-final-report.json) includes per-request retrieval, screening, generation and audit timings as observed.

The post-pilot offline suite passed **344 tests**, with **43 integrations deselected** and one existing Starlette/AnyIO deprecation warning. `pip check` and [Windows CI on the exercised application commit](https://github.com/momen320230161-hub/ShieldRAG/actions/runs/44749236504) passed. The historical report, release policy and private fixture manifests remain separate from this evidence. [PR #6](https://github.com/momen320230161-hub/ShieldRAG/pull/6) remains a draft for final review.
