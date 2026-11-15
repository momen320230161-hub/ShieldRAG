# Baseline RAG (Task 04)

Authenticated Admin explicitly authorizes external processing of an approved original. The backend acquires a database lease, downloads private bytes, verifies original SHA-256, extracts in an isolated subprocess, chunks deterministically, and requests Gemini document embeddings. It checks the original again before publishing the entire index in one database transaction. No database transaction remains open during extraction or Gemini calls.

Search embeds the question with `RETRIEVAL_QUERY`, calls the existing SECURITY INVOKER `match_shield_chunks` with the caller's bearer token and publishable key, and rechecks trusted profiles and source metadata. RLS allows only approved, fully indexed, hash-matched, externally authorized content: public for Students, public/restricted for Admins. The server key never authorizes retrieval. Query results from another embedding model are excluded. Changing model requires Admin reindexing; during a mixed-model transition irrelevant older vectors can reduce recall, so reindex all participating documents before switching deployments.

Ask sends bounded authorized excerpts as untrusted JSON data with a separate fixed system instruction. It uses no tools. An empty result causes a fixed abstention without a generation call. Generated evidence must reference an actual retrieved chunk and contain an exact contiguous quote. Backend citations contain database-derived document names, UUIDs and PDF page numbers. Sources and current roles are checked again after generation; permission changes or index replacements cause abstention.

## Models and bounds

- Official `google-genai==3.3.0`. `gemini-embedding-001`, exactly 768 values, document/query task types, finite/nonzero checks and manual L2 normalization. The stored float32 vector norm is checked transactionally. [Google embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings).
- Default generation: `gemini-3.5-flash-lite`, confirmed available with the configured key using an actual synthetic generation request. Both models are configurable. No automatic model fallback or dimension conversion.
- UTF-8 TXT; strict pypdf 7.1 PDF text extraction, page order and one page per chunk. No OCR, scripts, links, embedded programs or external PDF resources are executed.
- At most 10 MiB original, 200 PDF pages, 200,000 extracted characters, 128 chunks by default. Extraction: 15 seconds; full indexing: 180 seconds. Linux parser: 512 MiB address-space/15 CPU-second limits; Windows: subprocess timeout and parser decoding/work bounds, without a hard OS memory sandbox. [pypdf configuration](https://pypdf.readthedocs.io/en/7.1.0/modules/configuration.html).
- Chunk ceiling 550 whitespace words AND 1,800 UTF-8 bytes; overlap up to 80 words capped at one third of the preceding window. The byte bound deliberately produces smaller chunks than the suggested 500–800 tokens, especially for non-ASCII text, to conservatively stay below the embedding model's 2,048-token input limit without silently truncating. Oversized indivisible words fail explicitly. Repeated identical text is indexed once at its first page occurrence. No page-crossing chunks.
- Embeddings: batches of 8, provider concurrency 2 per process, at most 3 attempts for 429/500/502/503/504 with bounded exponential backoff. Permanent errors fail immediately. SDK internal retries disabled; 20-second provider timeout. Per-process 256-entry embedding cache uses model/task/content digest keys; raw text is not stored in cache keys. Cache/process restart can cause repeated calls; cached indexes avoid unchanged document embedding work.
- Question: 1–1,800 UTF-8 bytes, top_k 1–10 (default 5), similarity threshold default 0.35, context at most 12,000 characters. POST JSON bodies at most 8 KiB. Structured answer at most 4,000 characters. Settings enforce hard upper bounds.

## Index lifecycle and recovery

`not_indexed/failed → processing → indexed`; any confirmed processing failure transitions the owning lease to failed and removes hidden stale chunks. A concurrent job receives 409. Ten-minute leases allow recovery after a worker crash; retry after expiry. Publication requires the same job token, approved status, expected SHA and live Admin role. Insert/delete/state/audit changes commit together; malformed later chunks roll the whole publication back. Cached retries verify Storage integrity and preserve chunk IDs. Cached checks have operation tokens so an old failed check cannot invalidate a newer published index.

`document_index_started`, `document_indexed` and `document_index_failed` audit events contain static reasons and trusted actor/document references. Confirmed original-byte failures use the existing persistent integrity audit. An unavailable audit remains denied with 503. If failure cleanup itself is unavailable, logs identify the document UUID for reconciliation; its processing chunks remain hidden and the lease expires. A lost publication acknowledgement may return 503 even if committed; a subsequent retry verifies the cached index. No durable background job queue is added.

The forward migration `20261115143019_shieldrag_atomic_baseline_rag` adds document index metadata, three service-only SECURITY INVOKER RPCs and strengthens existing chunk RLS/RPC conditions. Existing tables and prior migrations are preserved. Previously seeded/legacy chunks lacking verified index metadata become invisible; they require explicit approved indexing. No production-like documents are reindexed automatically.

## External processing and remaining limits

`external_processing_authorized:true` is mandatory for each indexing request, including restricted documents. This records the authenticated Admin's affirmative authorization to send extracted text to Google's configured Gemini service. Asking/searching also sends the question and, for generation, authorized excerpts externally. Operators must authorize that service and applicable residency/retention terms before use. RLS controls database access; it does not supply third-party confidentiality or residency guarantees.

Known configured credentials and common secret/JWT formats are rejected before model calls; generated known credentials are denied. Validation and provider errors omit raw inputs and upstream diagnostics. These guards do not detect every unknown secret in arbitrary source text. Do not upload secrets; enforce suitable admission controls.

Citation existence and exact quotes are deterministic checks; semantic entailment of every generated claim is not guaranteed. Prompt injection, hallucination, malicious documents and misleading citations remain baseline risks despite instruction separation and RLS. There is no Task 05 classifier, security agent or evaluation system. Deploy behind HTTPS, per-user rate limits and resource controls; per-process concurrency is not a deployment-wide quota.

Chat endpoints are intentionally stateless. Existing chat tables contain content/owner fields but have no write policies, stored citation provenance or permission-aware history contract. Adding persistence safely expands scope; it remains a separate task. No chat history enters the prompt or bypasses current document permissions.

## Swagger walkthrough

Start the backend using [setup](backend-setup.md), open `/docs`, and authorize a synthetic account bearer token. Upload a PDF/TXT and approve as Admin. Call `POST /api/v1/documents/{id}/index` with `{"external_processing_authorized":true}` only after authorizing external transfer. Authorize Student or Admin and call `/api/v1/rag/search` or `/api/v1/rag/ask` with `{"question":"What does the approved document say?","top_k":5}`. See [API contracts](api-contracts.md) and [testing](testing.md).
