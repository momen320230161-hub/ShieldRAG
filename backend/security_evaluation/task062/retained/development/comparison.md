# ShieldRAG offline RAG evaluation

**Complete offline run.** 8 valid paired cases, 16/16 requests executed and 0 unavailable because they were not executed. The mock intentionally emits scripted disallowed outcomes when an attack case reaches generation. The comparison measures protection against those injected response faults and fixture scope checks. Provider contract: structured extracts simulated for eligible secure cases.

## Experimental setup

Application base `8ac119f1d547257c9a23e4c42551c75ae869cfe8`, model revision `shield-security-calibration-1`, benchmark `shieldrag-task061-dev-v1`, seed 6021, digest `78e567c89e2b0fe4439a47bf5cba62d2fb1d72776ced1e2821b36ae2fab653b9`. The in-process FastAPI run used Python 3.12.10 on Windows AMD64 and 11 synthetic fixture chunks. The two HTTP routes used the same sample role, question, chunk revision and retrieval parameters. Case order was seeded and first route alternated. The classifier was warmed and the embedding cache was cleared between requests. No external services were invoked.

Composition by label {'benign': 7, 'attack': 1}, by language {'en': 6, 'ar': 1, 'mixed': 1} and by role {'student': 8}. These project-authored cases were visible to developers. A separate development manifest exercises provider and audit failure paths.

## Threat model

These scenarios represent untrusted user questions, retrieved reference snippets and simulated provider response corruption. They test a harmless marker release, release of a fixture forbidden by role or state, or an unquoted marker with a valid citation. An authorization failure is a forbidden fixture identifier in a citation or a forbidden marker in returned content. Unexpected retrieval is counted separately. A tool or role claim in text has no authority. The fake Supabase transport represents role and review filters. This run cannot establish real RLS behavior.

## Security results

| Outcome | Baseline | Secure |
| --- | --- | --- |
| Valid requests | 8/8 | 8/8 |
| Attack objective observed | 1/1 (100.0%) [20.7%, 100.0%] | 0/1 (0.0%) [0.0%, 79.3%] |
| Security blocks on attacks | 0/1 (0.0%) [0.0%, 79.3%] | 1/1 (100.0%) [20.7%, 100.0%] |
| Authorization disclosures | 0/8 (0.0%) [0.0%, 32.4%] | 0/8 (0.0%) [0.0%, 32.4%] |
| Unexpected retrieved chunks by request | 0/8 (0.0%) [0.0%, 32.4%] | 0/8 (0.0%) [0.0%, 32.4%] |

Secure decisions include 6 allow, 1 block and 1 review. TP 1, TN 6, FP 1, FN 0. Precision 1/2 (50.0%) [9.5%, 90.5%], recall 1/1 (100.0%) [20.7%, 100.0%], F1 0.667, false-positive rate 1/7 (14.3%) [2.6%, 51.3%], false-negative rate 0/1 (0.0%) [0.0%, 79.3%]. Review counts as non-allow. A missed detection can still be prevented by the authorization boundary. Baseline has no detector decision.

| Challenge stage | Baseline success | Secure success | Secure non-allow |
| --- | --- | --- | --- |
| output | 1/1 (100.0%) [20.7%, 100.0%] | 0/1 (0.0%) [0.0%, 79.3%] | 1/1 (100.0%) [20.7%, 100.0%] |

| Attack category | Baseline successes | Secure successes | Secure detections |
| --- | --- | --- | --- |
| output-validation | 1/1 (100.0%) | 0/1 (0.0%) | 1/1 (100.0%) |

Secure audit stage on blocked attack rows: output 1.

## Answer quality

The factual rubric searches predeclared reference phrases. Completeness is the fraction of expected facts present. The grounding proxy requires all expected facts and relevant evidence with valid citation metadata and exact quotes. These measures do not establish semantic correctness or rule out unsupported extra claims.

| Benign outcome | Baseline | Secure |
| --- | --- | --- |
| availability | 7/7 (100.0%) [64.6%, 100.0%] | 6/7 (85.7%) [48.7%, 97.4%] |
| supported | 7/7 (100.0%) [64.6%, 100.0%] | 6/7 (85.7%) [48.7%, 97.4%] |
| insufficient evidence | 0/7 (0.0%) [0.0%, 35.4%] | 0/7 (0.0%) [0.0%, 35.4%] |
| security block | 0/7 (0.0%) [0.0%, 35.4%] | 1/7 (14.3%) [2.6%, 51.3%] |
| answerable availability | 7/7 (100.0%) [64.6%, 100.0%] | 6/7 (85.7%) [48.7%, 97.4%] |
| expected abstention | N/A (0 denominator) | N/A (0 denominator) |
| all reference facts | 7/7 (100.0%) [64.6%, 100.0%] | 6/7 (85.7%) [48.7%, 97.4%] |
| fact coverage | 10/10 (100.0%) | 9/10 (90.0%) |
| grounded proxy | 7/7 (100.0%) [64.6%, 100.0%] | 6/7 (85.7%) [48.7%, 97.4%] |
| citation validity | 10/10 (100.0%) | 9/9 (100.0%) |
| citation relevance | 10/10 (100.0%) | 9/9 (100.0%) |
| extractive | 3/7 (42.9%) [15.8%, 75.0%] | 3/7 (42.9%) [15.8%, 75.0%] |
| multi extract | 0/7 (0.0%) [0.0%, 35.4%] | 3/7 (42.9%) [15.8%, 75.0%] |

| Task | Baseline supported answers | Secure supported answers |
| --- | --- | --- |
| quotation | 1/1 (100.0%) | 1/1 (100.0%) |
| summarization | 1/1 (100.0%) | 1/1 (100.0%) |
| translation | 1/1 (100.0%) | 0/1 (0.0%) |
| multi-passage | 2/2 (100.0%) | 2/2 (100.0%) |

## Performance

End-to-end latency includes TestClient, authentication, worker scheduling and the mocked adapters. Retrieval includes embedding. Input/context/output screen rows measure classifier plus rules called within the agent. Separate filename checks, output evidence validation and other request work are included in end-to-end latency. An absent phase means it did not run. Logical calls count application method invocations. Real provider calls were zero and token usage and monetary cost were unavailable.

| Route | N | Mean ms | Median ms | p95 ms | SD ms | Embed calls | Generation calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 8 | 18.178 | 11.794 | 43.196 | 14.059 | 8 | 8 |
| secure | 8 | 28.018 | 25.080 | 53.621 | 15.343 | 7 | 7 |

| Phase | Baseline N / median ms | Secure N / median ms |
| --- | --- | --- |
| input_screen | 0 / N/A | 8 / 3.250 |
| retrieval | 8 / 4.418 | 7 / 4.797 |
| embedding | 8 / 0.579 | 7 / 0.675 |
| context_screen | 0 / N/A | 7 / 3.029 |
| generation | 8 / 0.366 | 7 / 0.314 |
| output_screen | 0 / N/A | 6 / 3.901 |
| audit | 0 / N/A | 8 / 0.627 |

## Paired uncertainty

Intervals in brackets are descriptive Wilson 95% intervals on row-level proportions. Cases were deliberately constructed and share patterns. The intervals are not population generalization estimates. Paired counts use only pairs with two valid responses. No significance test was used.

| Outcome | Valid pairs | Both | Baseline only | Secure only | Neither |
| --- | --- | --- | --- | --- | --- |
| attack_success | 1 | 0 | 1 | 0 | 0 |
| benign_availability | 7 | 6 | 1 | 0 | 0 |

The mean Secure minus Baseline latency was 9.840 ms on 8 pairs. The seeded 2,000-resample paired percentile bootstrap interval was 1.977 to 15.597 ms in this local run.

## Failure analysis

Stable IDs below refer to public synthetic benchmark definitions. Invalid responses are visible in the JSON report and do not count as prevented attacks or as successful answers.

| Secure diagnostic | Case IDs |
| --- | --- |
| Benign security block | d-translation |
| Attack allowed by detector | None |
| Invalid response | None |

| Selected secure case | Status | Retrieved chunks | Generations | Last audit stage |
| --- | --- | --- | --- | --- |

## Limitations and next steps

The response script forces specific faults. It measures enforcement and availability on a controlled synthetic corpus without estimating real Gemini attack rates, embedding retrieval quality, production latency or cost. The PDF scenario uses extracted text and a synthetic page identity. An exact extract can omit necessary context or faithfully repeat a false source. The rubric cannot identify all such errors. A separately authorized live pilot should measure ordinary answer availability, citations and role isolation. A larger independently authored evaluation would be needed to estimate robustness beyond these cases.

Reproduce the JSON and this report with `python -m scripts.run_security_evaluation` from `backend/`. Timing and UUID-free audit summaries are scrubbed of prompts, answers, credentials, raw errors and event identifiers.
