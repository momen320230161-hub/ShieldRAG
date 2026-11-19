# AI Security Agent (Tasks 05 and 05.1)

The branch loads the digest-pinned `shield-security-calibration-5` policy. It retains Task 05.1's coefficients, input/context thresholds and block cut. Exact output spans have a separately fitted review cut. Additional output rules block affirmative claims of changing privileges or relying on invalid authority. The audit schema version remains `shield-security-v1`. [Current release and earlier decisions](security-quality.md).

`POST /api/v1/rag/secure-ask` screens the question, sources and generated response. Both this endpoint and `/api/v1/rag/ask` use the same Supabase authentication, trusted profiles, caller-JWT retrieval, RLS, approved/indexed/hash/consent predicates and citation checks. The agent has no authority to grant roles or widen retrieval.

## Review findings

The original fixed test had seven benign non-allows. None hit a deterministic rule. Three crossed the block threshold and four entered the fixed 0.25-margin review band. The old TF-IDF model assigned positive weight to words such as “system,” “query,” “security” and “authorization,” which occur in attack instructions and ordinary course material. Even “use” contributed positively to a benign sorting statement. The question and source prose had different error patterns. For example, the paired RBAC and Arabic questions both passed input screening, but their source lines received review and block respectively. A single such chunk denies the entire request. Concatenating the answer and quotes also changed the classifier's feature input and could repeat a passage already evaluated as context.

The original `output_contamination` case passed input and context screening. The mock then returned a synthetic canary as its entire answer and a valid quote from the authorized source. The joined output scored about −0.7381, below the old review cutoff, and no rule matched. Shared citation validation checked the quote and source ID, then rechecked source permissions. It had no requirement connecting the answer text to that quote. The supported response therefore included the canary despite having a valid citation.

## Request policy

1. Screen the question before embedding. Screen all returned authorized chunks before generation. Check filenames separately with rules.
2. Any rule match blocks. For the classifier, margins at or above **−0.0328684301** block. Margins at or above **−0.1456773546** and below the block threshold return review. Lower margins pass this check and still require the other security checks. Both block and unresolved review withhold an answer. The thresholds apply across stages and the margins are uncalibrated.
3. If any chunk receives block or review, withhold the entire context. A later block outranks an earlier review after all authorized chunks have been evaluated. Continuing with a subset would change evidence availability and would depend on reliably identifying compromised sources. Safe chunks alongside an ambiguous chunk can still be lost under this policy.
4. For supported secure answers, Gemini is asked to copy one verbatim contiguous span. Require each exact quote and ID to match a screened authorized chunk, and require the trimmed answer to occur inside one of those submitted quotes. Apply rules to the individual quotes and apply rules and the classifier to the answer. Use the existing source-permission and current-content recheck before release. Reject unsupported additions, quote stitching and paraphrases that violate the span requirement. A quote from another part of the same source cannot validate the answer.
5. Confirm an audit write before release. With empty retrieval or a genuinely unsupported response, return insufficient evidence after the audit acknowledgement. Known unsafe output returns no raw text or citations. Provider, model and audit failures withhold the answer with a structured 503. Existing 401/403 behavior applies.

Rules still check configured secrets, credential-shaped strings, explicit disclosure requests and high-confidence authority/override patterns. They inspect at most four Base64 tokens of at most 4,096 characters and apply a bounded one-level decoding pass. Output checks cover both system-instruction variants and explicit first-person adoption of an instruction override. Ordinary security terminology alone is allowed by the rules. The classifier can still refuse ordinary content.

The extractive constraint reduces unquoted additions. It also rejects useful synthesis, translations and otherwise correct paraphrases. A valid span may answer the wrong question, omit a qualifier or reproduce misleading or undetected malicious content already present in a source. The span check verifies extractive grounding. Semantic entailment and comprehensive injection resistance remain unevaluated.

## Model and validation

Training compares balanced Logistic Regression with Linear SVM using the existing word TF-IDF 1–2 grams and character-within-word TF-IDF 3–5 grams, fixed feature caps and seed **1729**. Runtime and training share NFKC/case normalization and handling for combining marks, zero-width characters and Arabic tatweel.

The dataset contains **276** project-authored synthetic examples. Task 05.1 adds 24 training rows in eight families and 15 validation rows in five families. The additions use short questions, reference prose and extract-like responses in English, Arabic and mixed language. Topics include browser isolation, webhook signatures, measurement sciences and urban design. See `CALIBRATION_BENIGN` in `backend/app/security/dataset.py` for the complete provenance and stage assignments. No private data or external benchmark was used.

| Partition | Benign | Attacks |
| --- | ---: | ---: |
| Training | 102 | 63 |
| Validation | 42 | 21 |
| Frozen test | 24 | 24 |

Only training fits feature vocabulary, IDF and coefficients. The original test IDs, groups, labels and text are unchanged, with canonical test SHA-256 `8f9438cf60fe53634b206354a73278672a1aecf8fa9e611cf2a3a1f680bc2c6a`. New topics have separate development family IDs and normalized exact duplicate checks run across splits. The fixed test had already been read during Task 05 and the review. Its updated scores are a development comparison.

For each candidate, sweep validation score boundaries after combining margins with rule denials. The review threshold maximizes benign availability while preserving the old policy's 21/21 detection on validation. Ties prefer the highest qualifying threshold. Above that boundary, choose the block threshold by validation block macro-F1, then lower false-positive rate, greater recall and smaller absolute margin. Choose the candidate by combined non-allow availability first, then block metrics, with stable order for ties. All choices precede final-test scoring.

Linear SVM scored **21/21** validation attacks as non-allow with **6/42** false positives, versus **13/42** on the same expanded validation rows when scored with the old model and review cutoff. At the new block threshold, rule-or-margin blocks caught **20/21** and refused **5/42** benign rows (macro-F1 **0.8973**). Classifier-only validation at the block threshold caught **19/21** with **5/42** false positives.

The loaded scikit-learn 1.9.1 JSON model holds the bounded numeric feature and linear parameters. The revision `shield-security-calibration-1` has SHA-256 `92021975d6b1f5e6bc5f1fed836b502e2485126308b1c8dbc61c858f20306d85` and size 452,855 bytes. Runtime validates the trusted manifest, model revision, exact library version, bounds, shapes and finiteness. Training checks inference parity on all splits. The manifest's digest detects artifact damage relative to the trusted release. Code or manifest replacement is outside that integrity boundary. Loading takes place once per application instance with worker-thread inference limited to two concurrent analyses. A missing or invalid artifact fails closed on the secure endpoint.

## Measured comparison

| Frozen synthetic test (24 benign, 24 attacks) | Task 05 | Task 05.1 |
| --- | ---: | ---: |
| Classifier-only precision | 87.50% | 90.48% |
| Classifier-only recall | 87.50% | 79.17% |
| Classifier-only F1 | 87.50% | 84.44% |
| Classifier-only false positives | 3/24 | 2/24 |
| Classifier-only false negatives | 3/24 | 5/24 |
| Full-policy non-allow precision | 77.42% | 85.71% |
| Full-policy non-allow recall | 24/24 | 24/24 |
| Full-policy non-allow F1 | 87.27% | 92.31% |
| Full-policy false positives | 7/24 (29.17%) | 4/24 (16.67%) |

The remaining false positives include a database question and database prose, an explanation of Base64 and an authorization-related statement. Rules and reviews caught all classifier-only misses in this sample. Review remains a denial, and the classifier-only recall drop makes the combined policy essential. See the JSON reports for errors, direct/indirect breakdown and measured local inference time.

| Same controlled mock, five attacks and three benign questions | Baseline | Task 05 Secure | Task 05.1 Secure |
| --- | ---: | ---: | ---: |
| Attack success by exact synthetic canary | 4/5 | 1/5 | 0/5 |
| Security decision detected attacks | 0/5 | 4/5 | 5/5 |
| Benign supported answers | 3/3 | 1/3 | 2/3 |
| Valid citations among cited responses | 7/7 | 2/2 | 2/2 |
| Authorization failures | 0 | 0 | 0 |
| Logical embedding/generation calls | 10 / 7 | 7 / 2 | 7 / 3 |

The original mock contamination case now records `output/block/invalid_source_support` after generation. Equivalent unquoted additions and evidence laundering regressions also withhold output. The Arabic paired case still fails in context. These samples measure development behavior for a deliberately vulnerable mock, alongside a frozen test that has been inspected. Independent generalization and live attack rates remain unmeasured. Historical and current public reports are under `backend/security_evaluation/`, with original Task 05 reports preserved in `task05-baseline/`.

## Audit and reproduction

The deployed migration `20261115202657_shieldrag_security_agent_audit` and its `shield-security-v1` audit identifier still apply. The service-only RPC limits stages, actors, associations and static reason codes. UUID retry deduplication is preserved. Audit records contain IDs and bounded decisions/reasons, and exclude raw questions, chunks, answers, keys and scores. A missing audit acknowledgement prevents release. Authentication, RLS, private Storage and shared retrieval use their existing paths.

From `backend/` with Python 3.12 and the pinned lock:

```powershell
.venv/Scripts/python -m pip install -r requirements.lock
.venv/Scripts/python -m scripts.train_security
.venv/Scripts/python -m scripts.evaluate_security
.venv/Scripts/python -m scripts.compare_security
.venv/Scripts/python -m pytest -m 'not integration' -q -p no:cacheprovider
```

Training updates the bundled model and current public reports. The historical reports stay available for comparison. Review the reproduced digest and parity, allowing for numerical platform differences. See [testing](testing.md) for live opt-in fixtures and [verification](verification.md) for executed checks and blockers.
