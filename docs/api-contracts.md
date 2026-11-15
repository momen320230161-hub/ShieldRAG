# API contracts, version 1

Implemented routes appear in `/openapi.json` and `/docs`. All `/api/v1/` routes require `Authorization: Bearer <Supabase access token>`.

| Method and path | Success contract | Authorization |
| --- | --- | --- |
| `GET /health` | `200 {"status":"ok"}` | Public liveness |
| `GET /api/v1/me` | `200 {id,email,role,display_name}` | Registered user with trusted profile |
| `GET /api/v1/documents` | `200 {items:[Document],limit,offset}` | Student: approved public; Admin: approved public/restricted |
| `POST /api/v1/documents` | Multipart file + visibility; 201 DocumentMetadata | Registered Student/Admin |
| `GET /api/v1/documents/{id}` | 200 DocumentMetadata | Uploader, Admin, or other users for approved public metadata |
| `POST /api/v1/documents/{id}/approve` | JSON `{}`; 200 DocumentMetadata | Admin; pending state; stored hash verified |
| `POST /api/v1/documents/{id}/reject` | JSON `{reason:string}`; 200 DocumentMetadata | Admin; pending state |
| `GET /api/v1/security/events` | `200 {items:[SecurityEvent],limit,offset}` | Student: own events; Admin: all events |

List routes accept `limit` (default 20, range 1–100) and `offset` (default 0, nonnegative), ordered by descending `created_at`, then descending `id`. Pagination may shift with new rows. An empty list succeeds; no total count is returned.

`Document`: UUID `id`, string `original_name`, `visibility` (`public|restricted`), `review_status=approved`, `index_status` (`not_indexed|processing|indexed|failed`), RFC 3339 `created_at`. The list remains a retrieval catalog.

`DocumentMetadata`: UUID `id` and `uploaded_by`, `original_name`, `visibility`, nullable `sha256`, `review_status` (`pending|approved|rejected`), `index_status`, nullable UUID `reviewed_by`, nullable RFC 3339 `reviewed_at`, and `created_at`. Uploads always start pending/not_indexed with a non-null SHA-256. Metadata responses never return a Storage path, URL, bytes, or chunks. See [ingestion and review](document-ingestion.md) for validation, lifecycle, failure compensation, and exact requests.

`SecurityEvent`: UUID `id`, nullable UUID `user_id` and `document_id`, string `event_type`, `decision` (`allow|warn|review|deny`), nullable string `reason`, RFC 3339 `created_at`. Actor ownership controls event reads. Keep reasons free of secrets and document content.

Errors use FastAPI's `{detail:...}` envelope: 400 malformed/excess multipart data; 401 missing/invalid/expired JWT with a Bearer challenge; 403 denied permissions; 404 missing/hidden metadata; 409 review state/integrity conflicts; 413 upload size; 415 unsupported type; 422 invalid parameters/content; 503 configuration/upstream/uncertain completion.

The user-scoped gateway maps upstream 401 to 401 and permission 403 to 403. Recognized Auth codes `bad_jwt`, `session_expired`, `session_not_found`, and `user_not_found` also map to 401 when Auth returns 403. Rate limits, redirects, malformed responses and service/network failures become sanitized 503s. Privileged document-service credential failures become 503, since the user's token is already verified. Only the write RPC's whitelisted `PT403/PT404/PT409/PT422` codes map to client errors. Upstream bodies/credentials are never exposed. RLS may hide rows with a successful empty result.

## Future contracts — NOT implemented

These routes remain absent from OpenAPI and return 404/405:

| Route | Proposed request | Proposed success | Required enforcement |
| --- | --- | --- | --- |
| `POST /api/v1/chat/ask` | JSON `{question:string,session_id?:UUID}` (1–4000 characters) | `200 {session_id,answer,citations:[{document_id,chunk_id,page_number}]}` | Session ownership; approved user-scoped chunks; Student public-only |
| `POST /api/v1/evaluations/run` | JSON `{configuration:"baseline"|"secure"}` | `202 {id,status:"queued"}` | Admin; synthetic data; isolated jobs |

Task 04 implements the stateless RAG routes below. Session persistence, evaluation and the AI Security Agent remain future work.

## Baseline RAG routes

| Route | Request | Response / authorization |
| --- | --- | --- |
| `POST /api/v1/documents/{id}/index` | `{"external_processing_authorized":true}`; no extra fields | Admin, approved only. `200 {document_id,index_status:"indexed",chunk_count,embedding_model,dimensions:768,cached}` |
| `POST /api/v1/rag/search` | `{"question":"When does the archive open?","top_k":5}` | Authenticated. `200 {matches:[{chunk_id,document_id,document_name,page,content,similarity}]}` |
| `POST /api/v1/rag/ask` | Same question/top_k | Authenticated. `200 {answer,supported,citations:[{chunk_id,document_id,document_name,page,quote}]}` |

Questions are 1–1,800 UTF-8 bytes; top_k defaults to 5 and is bounded 1–10. Extra fields are rejected. JSON body limit 8 KiB, including streamed bodies. Validation returns `422 {detail:"Invalid request fields or limits"}` without echoing input. Index consent is explicit and mandatory; false/omitted consent fails. Student indexing is 403; unapproved/concurrent/integrity conflicts are 409. Missing/hidden document is 404. Provider, timeout and uncertain commit failures are sanitized 503.

Search returns an empty list below the configured threshold. Ask without usable supporting evidence returns `supported:false`, empty citations and `The answer cannot be determined from the available authorized documents.` No generation call occurs when search has no matches. PDF `page` is 1-based; TXT is null. Generated IDs are never accepted as database citations. These APIs do not create chat sessions or return signed Storage URLs. See [RAG architecture and limitations](rag.md).
