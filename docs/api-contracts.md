# API contracts, version 1

Implemented routes appear in `/openapi.json` and `/docs`. All `/api/v1/` routes require `Authorization: Bearer <Supabase access token>`.

| Method and path | Success contract | Authorization |
| --- | --- | --- |
| `GET /health` | `200 {"status":"ok"}` | Public liveness |
| `GET /api/v1/me` | `200 {id,email,role,display_name}` | Registered user with trusted profile |
| `GET /api/v1/documents` | `200 {items:[Document],limit,offset}` | Student: approved public; Admin: approved public/restricted |
| `GET /api/v1/security/events` | `200 {items:[SecurityEvent],limit,offset}` | Student: own events; Admin: all events |

List routes accept `limit` (default 20, range 1–100) and `offset` (default 0, nonnegative), ordered by descending `created_at`, then descending `id`. An empty list is a successful result. Pagination is offset based and can shift when rows are inserted. Authorization-filtered results may contain fewer than `limit` items. There is no total count.

`Document`: UUID `id`, string `original_name`, `visibility` (`public|restricted`), `review_status` (`approved`), `index_status` (`not_indexed|processing|indexed|failed`), RFC 3339 `created_at`. No storage path, hash, or chunk content is returned.

`SecurityEvent`: UUID `id`, nullable UUID `user_id` and `document_id`, string `event_type`, `decision` (`allow|warn|review|deny`), nullable string `reason`, RFC 3339 `created_at`. Event reasons must never contain passwords, tokens or document content; event production belongs to a future task.

Errors use FastAPI's `{detail:...}` envelope: `401` for missing/invalid/expired bearer tokens with `WWW-Authenticate: Bearer`; `403` for missing/unsupported trusted role or anonymous account; `422` for invalid query parameters; `503` for unavailable or failed Supabase operations, with sanitized messages. Auth is checked before protected reads. Supabase outages fail closed.

## Reserved future contracts — NOT implemented

These routes have no handlers and are absent from OpenAPI. Calls currently return `404` or `405`; the following contracts are design targets, not working features.

| Route | Proposed request | Proposed success | Required enforcement |
| --- | --- | --- | --- |
| `POST /api/v1/documents` | multipart `file` (PDF/plain text, max 10 MiB), `visibility` (`public|restricted`) | `201 {id,review_status:"pending",index_status:"not_indexed"}` | Authenticated registered user; uploader assigned from identity; hash computed server-side; private upload; no client review/role fields |
| `POST /api/v1/documents/{id}/approve` | JSON `{}` | `200 {id,review_status:"approved",reviewed_by,reviewed_at}` | Admin dependency before any privileged operation; UUID id; hash required; transactional review and audit |
| `POST /api/v1/documents/{id}/reject` | JSON `{reason:string}` (1–1000 characters) | `200 {id,review_status:"rejected",reviewed_by,reviewed_at}` | Admin dependency; transactional review and audit |
| `POST /api/v1/chat/ask` | JSON `{question:string,session_id?:UUID}` (question 1–4000 characters) | `200 {session_id,answer,citations:[{document_id,chunk_id,page_number}]}` | Session ownership; approved chunks only; student public only; user-scoped search RPC; no supplied role, embeddings, or arbitrary context |
| `POST /api/v1/evaluations/run` | JSON `{configuration:"baseline"|"secure"}` | `202 {id,status:"queued"}` | Admin dependency; synthetic datasets; isolated jobs |

Future writes reject unknown fields, return `409` for invalid state transitions and use the existing error envelope. Implement database write policies/authorized server operations and audit writes before enabling these contracts. No upload, review, chat, evaluation, or role mutation endpoint exists today.
