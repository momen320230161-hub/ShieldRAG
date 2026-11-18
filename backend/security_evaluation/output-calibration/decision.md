# Exact-span release decision

**OFFLINE QUALITY GATES PASSED — LIVE EVALUATION PENDING AUTHORIZATION.** The branch selects `shield-security-calibration-5` (E), SHA-256 `fa68f0c166edf201a0a80412f53bb10ef5c863f05f6306d9d1e81d4e29c3887e`.

E uses the merged classifier's vocabulary, IDF, coefficients, input/context decisions and block cut (−0.03286843). The review cut for exact output spans moves from −0.14567735 to −0.08979763. The fit recovered six of 68 calibration spans under a predeclared cap and a minimum review band. Every incumbent classifier block remains a block. Additional output rules withhold affirmative claims that a read-only answering service changed privileges or relied on invalid authority. A rule match outranks any model decision. The deployed artifact is bounded numeric JSON. There is one classifier inference per screened batch and no additional provider call.

## What failed before promotion

A threshold-only fit stopped before qualification because A allowed a claim of having elevated the caller's role. Candidate D added the privilege-change guard. It passed the historical availability gate but caught only 9/10 qualification controls. Its miss was a mixed-language claim of accepting forged administrator approval. A also missed it. D was rejected. E adds a denial for affirmative claims of accepting invalid authorization. E uses the identical numerical cuts and coefficients as D. The 48 project questions and the 10 output controls became regression evidence for E. The external QA confirmation was specified before examining external outcomes. [Original fit and lock](lock.json) · [D's failed confirmation](verification.json) · [E confirmation procedure](confirmation.md).

| Offline evidence | Merged A | Current E |
| --- | ---: | ---: |
| Historical supported answers | 9/22 | 11/22 |
| Historical scripted attack objectives achieved | 0/22 | 0/22 |
| Current citations valid on historical benign answers | 9/9 | 11/11 |
| Project questions authored for this round | 30/48 | 32/48 |
| Previous qualification questions | 15/18 | 16/18 |
| Separate schema-aware excerpt suite, benign supported | 6/7 | 6/7 |
| XQuAD English, grounded answers | 863/1,190 (72.5%) | 925/1,190 (77.7%) |
| XQuAD Arabic, grounded answers | 784/1,190 (65.9%) | 835/1,190 (70.2%) |

All individual previously supported cases were retained in each comparison. The two recovered historical answers concerned permissions and roles. The 48-question cohort gained one Arabic and one mixed-language answer. E withheld 10/10 calibration and 10/10 qualification output controls, retained the established Arabic educational allow, and withheld every known contamination objective. No synthetic request returned an unauthorized source or citation. Every secure response in the paired harness required an acknowledged audit. [Project evidence](confirmed/verification.json).

## Independent answer-availability evidence

All original 1,190 questions in **each** of the parallel English and Arabic XQuAD editions ran through both FastAPI routes with each policy. Every source was a contiguous window of up to 380 characters around the published answer offset. All annotations aligned verbatim, with no repairs or exclusions. The same mocked generator returned the gold span for both policies. Each language gained supported answers and lost zero. The 2,380 language rows represent 1,190 underlying questions. This measures screening loss on answer-bearing passages with ideal retrieval and gold generation. Actual retrieval recall, Gemini quality and adversarial robustness are outside this measurement. Historical and project security cases are developer-visible, and wording outside the read-only rules can still be misclassified. In particular, Arabic XQuAD is not a mixed-language security benchmark. [External counts and changed IDs](confirmed/xquad.json) · [XQuAD, Artetxe, Ruder and Yogatama, CC BY-SA 4.0](https://github.com/google-deepmind/xquad/tree/7d30520c717524000f0d9d2f9c10a069acd9d285).

## Reproduction

From `backend`, using the locked Python 3.12 environment:

~~~powershell
.venv/Scripts/python -m scripts.calibrate_output fit --bundle-dir .integration/output-release-repro
.venv/Scripts/python -m scripts.calibrate_output verify --bundle-dir .integration/output-release-repro --output-dir .integration/output-D
.venv/Scripts/python -m scripts.calibrate_output confirm --bundle-dir .integration/output-release-repro --output-dir .integration/output-E
git clone https://github.com/google-deepmind/xquad.git .integration/output-xquad
git -C .integration/output-xquad checkout --detach 7d30520c717524000f0d9d2f9c10a069acd9d285
.venv/Scripts/python -m scripts.confirm_xquad --data-dir .integration/output-xquad --output .integration/xquad-confirmation.json
.venv/Scripts/python -m pytest -m 'not integration' -q -p no:cacheprovider
.venv/Scripts/python -m pip check
~~~

The D verification command intentionally exits 1 and preserves its failed result. Run the E command separately. Both data files are digest-verified before scoring. Only metrics and changed upstream IDs are committed. The external source checkout and generated work files reside under the ignored integration directory.

## Bounded live proposal awaiting owner approval

Use the previously scoped seven case pairs (14 asks), two synthetic Student/Admin accounts and eight one-chunk text documents. Exercise the public, restricted, mixed-language, translation and multi-excerpt paths. At most eight document embeddings, 14 query embeddings and 14 generations (36 logical calls and up to 108 application attempts). Expected writes include Auth users/profiles, the fixture helper's six seeded authorization documents/chunks, eight private objects, document/review/index rows and application audits. Record the owned IDs before each step. Verify the target project and absence of unrelated eligible rows. Sign out, remove only recorded objects, events, chunks and documents, then run the guarded seed/account cleanup. Independently verify zero remaining owned IDs and compare bucket/policy snapshots. Quota, charges, timeouts and partial cleanup are the operational risks. This run requires separate owner authorization. Task 06 made no live calls in this round.
