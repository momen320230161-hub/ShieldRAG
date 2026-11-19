# Task 06 security evaluation

The current release compares the merged 05.1 incumbent, a rejected output calibration and the selected read-only output policy. The external comparison uses every English and Arabic XQuAD question with gold-span generation through the local HTTP routes. [Results and validation limits](../backend/security_evaluation/output-calibration/decision.md).

Task 06.2 compared three versioned model bundles on 18 fresh question/passage/span groups and 12 control texts before replaying the original 44 historical pairs. The independent unit is a question family. A question, its passage and its answer count as a single availability outcome. The retained, rejected and historical results are available side by side. [Release comparison](../backend/security_evaluation/task062/decision.md) · [Earlier Task 06.1 results](security-quality.md#historical-task-061-secure-rag-quality-and-security).

Task 06 compares the existing authenticated Baseline and Secure RAG routes. The offline runner calls the real FastAPI routes, security agent, citation checks and audit client. An in-process Supabase transport models caller identity, fixture scope and audit acknowledgements. A fake Gemini SDK returns scripted responses through the real Gemini parsing and validation code. The comparison therefore exercises application enforcement against controlled faults. It measures neither Gemini's probability of producing those faults nor real database isolation.

## Reproduce the offline run

From the backend directory at historical commit `5d13a56` with Python 3.12 and the existing backend lock installed:

~~~powershell
.venv/Scripts/python -m scripts.run_security_evaluation
.venv/Scripts/python -m pytest -q -m 'not integration' -p no:cacheprovider
~~~

The run always uses the checked-in synthetic manifest and its seeded order. No local environment file or provider credential is needed. It publishes sanitized JSON and Markdown under backend/security_evaluation/task06/reports. The optional plotting command uses a separate installation in the local virtual environment:

~~~powershell
.venv/Scripts/python -m pip install matplotlib==3.10.8
.venv/Scripts/python -m scripts.plot_security_evaluation
~~~

- [Benchmark manifest](../backend/security_evaluation/task06/benchmark/manifest.json)
- [Separate development manifest](../backend/security_evaluation/task06/benchmark/development.json)
- [Academic comparison with denominators and uncertainty](../backend/security_evaluation/task06/reports/comparison.md)
- [Machine-readable results](../backend/security_evaluation/task06/reports/results.json)
- [Comparison figures](../backend/security_evaluation/task06/reports/comparison.png)

## Experimental controls

The 44-case versioned benchmark has 22 benign and 22 attack-objective cases. It covers academic and security vocabulary, English/Arabic/mixed-language examples, quotations, summarization, multi-passage synthesis, translation, authorization and controlled response faults. Marker values are harmless simulation labels. The PDF case represents post-extraction text at a known page. Case authors inspected the new cases while developing the framework. They are separate from Task 05 training and evaluation examples, with an exact normalized overlap check, and have no external or blinded provenance. Task 06 does not tune the security model or thresholds.

Both routes receive the same trusted role, question, selected fixture corpus and pinned content revision for a pair. The transport tests caller-JWT reads separately from the existing service-only simulated audit acknowledgement. Unexpected retrieval and forbidden output are tracked independently. The mock does not widen read scope, add attacker instructions to the production system prompt, or call a network provider. It deliberately emits disallowed synthetic outcomes for designated cases if generation is reached. Such scripted behavior exposes what each pipeline does with the same bad response. It does not estimate actual attack success. Reported detection counts include reviews, while a missing or invalid response contributes to the attempted total and is excluded from paired success denominators. An authorized abstention can prevent exposure without a detector block.

The quality rubric checks declared phrases and relevant verified citations. It exposes missed reference facts and the availability cost of rejecting useful paraphrases, translations and synthesis. It cannot independently find all hallucinations, omissions or contradictions. No model judge is used. Wilson intervals and the seeded paired latency bootstrap describe this fixed experiment with small and sometimes related classes. No population significance test is claimed.

The JSON has no raw prompt, response, quote, credential or audit event ID. Retrieved IDs are deterministic synthetic chunk UUIDs. Phase timers observe existing code locally and can overlap, particularly retrieval and embedding. Screening timers cover classifier plus rules inside the agent. Output evidence checks, filename rules and current-source checks also contribute to end-to-end latency. Logical provider method calls, physical requests and billing are distinct. Physical provider calls were zero in this run, and live token counts and costs remain unavailable.

## Evaluation persistence

The existing evaluation_runs table has Admin SELECT under RLS and no ordinary application write path. The offline runner stores versioned JSON and a Markdown report in the repository. No migrations, privileged write endpoints or changes to RLS are needed.

## Live pilot proposal awaiting separate authorization

The earlier Task 05.1 approval applies only to that earlier run. This pilot is an operator procedure and requires new approval for bounded Gemini use, temporary Auth/database writes and Storage uploads. It probes ordinary answer quality and authorization. Scripted contamination remains an offline test.

- **Seven paired cases (14 RAG requests).** Use b-summary, b-join, b-translate, b-quote, b-ar, b-admin and a-restricted-record from the manifest. The last two ask the same question as Admin and Student against the same private fixture. Alternate which route runs first. Compare statuses, fixture IDs, source quote and page and apply the same predeclared facts rubric locally.
- **Two fresh synthetic accounts and eight TXT files.** Use the existing guarded account fixture procedure with a new run ID, after confirming project bnehmoxpzycxnsdxxfxc and zero collision for exact IDs and paths. If using the stock fixture generator, its six extra synthetic RLS document and chunk rows use the marker and mock embedding model excluded by the application's Gemini retrieval validation. Confirm no unrelated document can reach the evaluation model before indexing or querying. Upload only the eight short sources through the private Storage ingestion route, verify their hashes, approve and index them as Admin with explicit external-processing consent. Record exact UUIDs, Storage keys and fixture ownership and verify one chunk per TXT file. Use the signed account JWTs for normal HTTP requests.
- **Provider budget.** At most eight single-batch indexing embeddings plus 14 query embeddings plus 14 generations gives 36 logical provider operations. With the current application's maximum of three attempts for retryable failures, the upper bound is 108 application-initiated provider attempts. The plan excludes extra search, repeated indexing and manual reruns. Stop on unresolved quota or scope faults. Measured billing is unavailable.
- **Teardown.** Revoke both synthetic sessions. Inventory each case's exact document, chunk, upload and event IDs before teardown. Validate the new owner IDs, run marker and canonical Storage keys, remove exact owned Storage objects through the API, then the associated chunk, application audit and document rows. Use the matching guarded cleanup SQL for the original generated account fixtures. Compare pre/post bucket setting and grants, and independently verify zero remaining matching users, profiles, sessions, documents, chunks, app audit records and Storage objects. Retain a private recovery manifest only while cleanup is unresolved. Preserve the platform's managed Auth audit logs.

The pilot has not been executed. If authorized later, record actual request and valid-case denominators, cleanup and real provider observations separately from the offline benchmark.
