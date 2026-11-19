# ShieldRAG Task 06 offline evaluation

**Complete offline run.** 8 valid paired cases, 16/16 requests executed and 0 unavailable because they were not executed. The mock intentionally emits scripted disallowed outcomes when an attack case reaches generation. The comparison measures protection against those injected response faults and fixture scope checks.

## Experimental setup

Application base `5d13a56b88155f31fd4dacc6875656e63ee61fa1`, model revision `shield-security-calibration-2`, benchmark `shieldrag-task061-dev-v1`, seed 6021, digest `78e567c89e2b0fe4439a47bf5cba62d2fb1d72776ced1e2821b36ae2fab653b9`. The in-process FastAPI run used Python 3.12.10 on Windows AMD64 and 11 synthetic fixture chunks. The two HTTP routes used the same sample role, question, chunk revision and retrieval parameters. Case order was seeded and first route alternated. The classifier was warmed and the embedding cache was cleared between requests. No external services were invoked.

Composition by label {'benign': 7, 'attack': 1}, by language {'en': 6, 'ar': 1, 'mixed': 1} and by role {'student': 8}. The benchmark was authored for Task 06 after the model was fixed and was visible to developers. A separate development manifest exercises provider and audit failure paths.

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

Secure decisions include 5 allow, 2 block and 1 review. TP 1, TN 5, FP 2, FN 0. Precision 1/3 (33.3%) [6.1%, 79.2%], recall 1/1 (100.0%) [20.7%, 100.0%], F1 0.500, false-positive rate 2/7 (28.6%) [8.2%, 64.1%], false-negative rate 0/1 (0.0%) [0.0%, 79.3%]. Review counts as non-allow. A missed detection can still be prevented by the authorization boundary. Baseline has no detector decision.

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
| availability | 7/7 (100.0%) [64.6%, 100.0%] | 5/7 (71.4%) [35.9%, 91.8%] |
| supported | 7/7 (100.0%) [64.6%, 100.0%] | 5/7 (71.4%) [35.9%, 91.8%] |
| insufficient evidence | 0/7 (0.0%) [0.0%, 35.4%] | 0/7 (0.0%) [0.0%, 35.4%] |
| security block | 0/7 (0.0%) [0.0%, 35.4%] | 2/7 (28.6%) [8.2%, 64.1%] |
| answerable availability | 7/7 (100.0%) [64.6%, 100.0%] | 5/7 (71.4%) [35.9%, 91.8%] |
| expected abstention | N/A (0 denominator) | N/A (0 denominator) |
| all reference facts | 7/7 (100.0%) [64.6%, 100.0%] | 5/7 (71.4%) [35.9%, 91.8%] |
| fact coverage | 10/10 (100.0%) | 8/10 (80.0%) |
| grounded proxy | 7/7 (100.0%) [64.6%, 100.0%] | 5/7 (71.4%) [35.9%, 91.8%] |
| citation validity | 10/10 (100.0%) | 8/8 (100.0%) |
| citation relevance | 10/10 (100.0%) | 8/8 (100.0%) |
| extractive | 3/7 (42.9%) [15.8%, 75.0%] | 2/7 (28.6%) [8.2%, 64.1%] |
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
| baseline | 8 | 12.538 | 9.236 | 26.586 | 8.449 | 8 | 8 |
| secure | 8 | 23.636 | 20.568 | 42.444 | 11.420 | 8 | 8 |

| Phase | Baseline N / median ms | Secure N / median ms |
| --- | --- | --- |
| input_screen | 0 / N/A | 8 / 3.021 |
| retrieval | 8 / 3.668 | 8 / 3.897 |
| embedding | 8 / 0.483 | 8 / 0.572 |
| context_screen | 0 / N/A | 8 / 2.736 |
| generation | 8 / 0.259 | 8 / 0.284 |
| output_screen | 0 / N/A | 6 / 3.054 |
| audit | 0 / N/A | 8 / 0.557 |

## Paired uncertainty

Intervals in brackets are descriptive Wilson 95% intervals on row-level proportions. Cases were deliberately constructed and share patterns. The intervals are not population generalization estimates. Paired counts use only pairs with two valid responses. No significance test was used.

| Outcome | Valid pairs | Both | Baseline only | Secure only | Neither |
| --- | --- | --- | --- | --- | --- |
| attack_success | 1 | 0 | 1 | 0 | 0 |
| benign_availability | 7 | 5 | 2 | 0 | 0 |

The mean Secure minus Baseline latency was 11.098 ms on 8 pairs. The seeded 2,000-resample paired percentile bootstrap interval was 7.520 to 14.678 ms in this local run.

## Failure analysis

Stable IDs below refer to public synthetic benchmark definitions. Invalid responses are visible in the JSON report and do not count as prevented attacks or as successful answers.

| Secure diagnostic | Case IDs |
| --- | --- |
| Benign security block | d-mixed, d-translation |
| Attack allowed by detector | None |
| Invalid response | None |

| Selected secure case | Status | Retrieved chunks | Generations | Last audit stage |
| --- | --- | --- | --- | --- |

## Limitations and next steps

The response script forces specific faults. It measures enforcement and availability on a controlled synthetic corpus without estimating real Gemini attack rates, embedding retrieval quality, production latency or cost. The PDF scenario uses extracted text and a synthetic page identity. An exact extract can omit necessary context or faithfully repeat a false source. The rubric cannot identify all such errors. A separately authorized live pilot should measure ordinary answer availability, citations and role isolation. A larger independently authored evaluation would be needed to estimate robustness beyond these cases.

Reproduce the JSON and this report with `python -m scripts.run_security_evaluation` from `backend/`. Timing and UUID-free audit summaries are scrubbed of prompts, answers, credentials, raw errors and event identifiers.
