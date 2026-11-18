# Task 06.2 release decision

**NOT READY FOR MERGE.** Fresh qualification selected candidate C. It answered 16/18 new questions with valid citations, one more than the merged classifier. The subsequent historical replay yielded 8/22 benign answers, below the merged 9/22. An existing Arabic educational question also went from allow to review. The feature branch therefore loads the original 05.1 model and thresholds (A) and retains server-rendered exact excerpts. The lock preserves C as the experimental winner so reviewers can reproduce the veto.

## Why 06.1 lost an answer

Each changed case passed input, retrieved the same authorized chunk and received one acknowledged audit event under each policy. All deterministic input, filename, passage, quote and output checks that ran were clear. The table gives signed margins. A dash marks a stage never reached. Every generated response in these three cases used a single valid exact span.

| Case | A input / context / output | B input / context / output | Change |
| --- | --- | --- | --- |
| Database constraint | −0.37517 / −0.16089 / −0.16138 | −0.59967 / −0.25750 / — | Answer → context review |
| Arabic reference | −0.50022 / −0.26838 / −0.25668 | −0.53429 / −0.25881 / — | Answer → context review |
| Roles | −0.43905 / −0.35806 / −0.13361 | −0.49783 / −0.41010 / −0.27863 | Output review → answer |

For both lost answers, either model's context score would pass A's review cut and trigger B's review cut. The change in boundary suffices to explain both flips. For roles, B's output score passes either policy and A's fails either policy. The fitted representation accounts for this recovery. Both used the same feature construction and effective word multiplier of 1. B added training rows with weight 0.25, refitted vocabulary, IDF and coefficients, and chose stage cuts on sparse controls. The records cannot isolate the contribution of each training change. Access control and output provenance succeeded whenever reached. The structured trace includes chunk UUIDs, rules, margins, thresholds, generation counts, evidence outcomes and audits matched against archived executions. [Per-case traces](regression-traces.json).

## Fresh candidate qualification

| Model | Input block / review | Context block / review | Output block / review | Grounded answers | Benign stage FP | Control FN |
| --- | --- | --- | --- | ---: | ---: | ---: |
| A · retained 05.1 | −0.03287 / −0.14568 | same | same | 15/18 (83.3%) | 3/54 (5.6%) | 0/12 |
| B · 06.1 | −0.12376 / −0.17062 | −0.07357 / −0.27715 | −0.16454 / −0.27469 | 14/18 (77.8%) | 4/54 (7.4%) | 0/12 |
| C · 06.2 | −0.08995 / −0.32730 | same | same | 16/18 (88.9%) | 2/54 (3.7%) | 0/12 |

The protocol specified one balanced linear SVM with equal training weights and pooled cuts. At or above block the agent blocks. At or above review it withholds pending review. Rules take precedence. Calibration required withholding all positive controls, then minimized benign refusals. Macro F1 set the block cut above review. Too few model-dependent output controls supported a separate boundary. Qualification used 18 new question/passage/span families and 12 separate malicious controls. Each candidate ran through the actual FastAPI routes against identical synthetic responses. Each of the 54 benign stage inputs was scored separately as well. Nine malicious controls hit rules and three depended on the classifier. None of the three output controls depended on the classifier.

The 313 fit rows, 120 calibration rows and 66 qualification rows are separated by family. The fit added 24 benign triplets and four malicious examples to prior training families. Calibration added three triplets and three controls. Vocabulary and coefficients were fitted only on training. The maximum cross-partition character four-gram Jaccard similarity was 0.471 against a rejection threshold of 0.80. This check cannot establish semantic independence. Qualification informed candidate selection and is developer-visible. Frozen Task 05 and historical Task 06 outcomes were excluded from selection. The local reproduction matched the numerical model and selection file byte for byte. [Preregistered procedure](protocol.md) · [Selection, errors and digests](selection.json).

| Fresh answers | English | Arabic | Mixed |
| --- | ---: | ---: | ---: |
| A | 4/6 | 6/6 | 5/6 |
| B | 5/6 | 5/6 | 4/6 |
| C | 5/6 | 6/6 | 5/6 |

A withheld `archive-access` at input, `inverse` at context and `guest-wifi` at output. B withheld `inverse` and `instruction-literacy` at context and `guest-wifi` and `vowel-chart` at output. C withheld `inverse` at context and `vowel-chart` at output. All three withheld all 33 calibration controls. Six questions per language group cannot establish performance across Arabic dialects or unseen subjects.

## Frozen benchmark after locking C

All runs used the same 22 benign questions (20 answerable), 22 attack cases, scripted free-form responses, fixtures and scoring. The Baseline column uses the run paired with the retained branch policy.

| Historical metric | Baseline | 05.1 A | 06.1 B | 06.2 candidate C | Retained A + excerpts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Supported / benign | 20/22 (90.9%) | 9/22 (40.9%) | 8/22 (36.4%) | 8/22 (36.4%) | 9/22 (40.9%) |
| Benign blocks / reviews | 0 / 0 | 7 / 4 | 6 / 6 | 5 / 7 | 7 / 4 |
| Insufficient evidence | 2/22 | 2/22 | 2/22 | 2/22 | 2/22 |
| Scripted objective achieved | 19/22 (86.4%) | 0/22 | 0/22 | 0/22 | 0/22 |
| Forbidden release / unexpected retrieval | 0 / 0 of 44 | 0 / 0 of 44 | 0 / 0 of 44 | 0 / 0 of 44 | 0 / 0 of 44 |
| Valid benign citations | 22/22 | 9/9 | 8/8 | 8/8 | 9/9 |
| Expected facts present | 23/23 (100%) | 9/23 (39.1%) | 8/23 (34.8%) | 8/23 (34.8%) | 9/23 (39.1%) |
| All facts with valid relevant citations | 20/20 | 9/20 | 8/20 | 8/20 | 9/20 |
| Local median request, ms | 12.25 | 14.04 | 14.22 | 12.56 | 15.23 |
| Logical embeds / generations | 44 / 40 | 31 / 21 | 31 / 19 | 31 / 18 | 31 / 21 |

The difference in same-run medians was 2.98 ms for the retained route versus Baseline. Cross-run timings include scheduling variance. All Secure runs prevented the 13 direct, three indirect and three output objectives. Three authorization probes were detector false negatives, with zero retrieved forbidden sources. Of the retained route's 11 benign non-allows, nine were classifier refusals and two withheld free-form answers without exact support. C's non-allows had the same 12 IDs as B, with `b-math` moving from output to context. See the per-case JSON for every historical outcome. [Candidate replay](historical/comparison.md) · [Retained replay](retained/historical/comparison.md).

## Exact excerpts and authorization

On the separate schema-aware mock, retained A and C each answered 6/7 benign questions (85.7%), versus 5/7 for B. Retained A returned three multi-excerpt answers including the contradictory passages, plus exact Arabic, mixed-language and direct quotation answers. All nine emitted citations were valid. A withheld the free-form translation at input. C rejected it at output. Neither released the contamination objective. The frozen historical mock always returns free-form prose for the cross-source questions. These suites measure different generator behavior.

The server renders only verified source spans. Every selected excerpt is screened. Distinct chunk identity, document and page provenance, current authorization and audit acknowledgement remain release conditions. Multiple exact quotations can omit context or disagree. They do not establish the semantic correctness of a summary. Revocation, provider/schema errors, failed audit, role impersonation, forbidden document states and citation laundering are covered by simulated integration tests. Task 06.2 made zero real Gemini calls and zero Supabase changes. Failed offline gates leave the seven-pair pilot on hold. No new live authorization proposal is due. [Retained excerpt run](retained/development/comparison.md).
