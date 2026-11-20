# Task 06.3 live comparison

**NOT READY FOR MERGE.** The single authorized pilot stopped while indexing the first source. Windows denied access to a named pipe needed by the extraction worker (`WinError 5`). Upload and Admin approval had succeeded for that source. No source reached the indexed state.

| Case | Intended observation | Baseline `ask` | Secure `secure-ask` |
| --- | --- | --- | --- |
| `d-thermal` | Facts from both expected sources | Not executed | Not executed |
| `d-mixing` | Multi-Excerpt Grounding | Not executed | Not executed |
| `d-ar` | Answer availability for Arabic input | Not executed | Not executed |
| `d-mixed` | Answer availability for mixed-language input | Not executed | Not executed |
| `d-translation` | Translation behavior under the existing grounding rules | Not executed | Not executed |
| `b-admin` | Restricted source available to Admin | Not executed | Not executed |
| `a-restricted-record` | Restricted source excluded for Student | Not executed | Not executed |

Baseline executed **0 of 7** planned requests. Secure executed **0 of 7**. Supported answers, blocks, reviews, false positives, safe abstentions, citation validity and relevance, source disclosures, audit acknowledgements and response latency are unmeasured.

Real Student and Admin JWTs and scoped PostgREST and vector RPC reads passed their checks on six synthetic authorization fixtures. The two configured Gemini models returned HTTP 200 for metadata reads. The application made zero Gemini embedding or generation calls, with zero provider attempts and retries. Tokens and cost were unmeasured.

The earlier offline Policy E results remain in the [offline evaluation](../../../docs/security-evaluation.md). The [pilot runbook](../../../docs/task063-live-verification.md) covers the failure, cleanup and remaining verification.
