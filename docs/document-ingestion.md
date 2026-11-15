# Secure document ingestion and review

Task 03 is backend-only. It stores validated original bytes and metadata; it does not extract text, chunk, embed, index, call Gemini, or generate answers.

## Configuration and migration

Use the existing backend setup. Configure `SUPABASE_SECRET_KEY` with a modern `sb_secret_...` key in private `backend/.env` or root `.env`. Settings load both using absolute repository paths; process environment variables override backend settings, and backend settings override root settings. Reads continue to use the caller's bearer JWT and RLS. Writes return 503 if the server credential is absent; read routes and health remain available. Never put the key in a client, response, terminal output, or Git.

Migration `20261114141719_shieldrag_secure_document_ingestion` adds only two database functions. It is already applied to the existing cloud project; do not replay it there. The original two migrations, tables, RLS policies, and private bucket are preserved. The new functions are `SECURITY INVOKER`, have an empty fixed search path, and grant execution only to `service_role`. An ordinary authenticated user, including an Admin JWT, cannot invoke them directly. Python validates identity/permissions before using its server credential; the functions independently verify trusted actor roles.

The local Supabase CLI package could not provide its Windows binary in this environment. The connected Supabase migration tool generated the applied version, which was then exported into the repository without altering existing history.

## API

All routes below require `Authorization: Bearer <Supabase user access token>`. Use `/docs` to authorize and test without a frontend.

| Route | Request | Response |
| --- | --- | --- |
| `POST /api/v1/documents` | Multipart: exactly one `file`; optional `visibility=public|restricted` (default public) | 201, safe document metadata |
| `GET /api/v1/documents/{id}` | UUID path parameter | 200 metadata, or 404 when missing/hidden |
| `POST /api/v1/documents/{id}/approve` | Admin JWT and JSON `{}` | 200 approved metadata; conflicts return 409 |
| `POST /api/v1/documents/{id}/reject` | Admin JWT and JSON `{"reason":"Safe review summary"}` | 200 rejected metadata; conflicts return 409 |

Upload and metadata responses contain `id`, `uploaded_by`, `original_name`, `visibility`, `sha256`, `review_status`, `index_status`, `reviewed_by`, `reviewed_at`, and `created_at`. Reviewer fields are initially null. No Storage path, URL, bytes, or raw chunks are returned. The existing list route stays an approved-only retrieval catalog; the new detail route allows uploaders to inspect their own pending/rejected metadata, Admins to inspect all metadata, and other users to inspect approved public metadata. The uploader's broader metadata rights do not grant restricted chunk/content access.

`uploaded_by`, role, hash, status, reviewer, timestamps, and Storage keys are server-controlled. Extra multipart fields, duplicate/multiple files, and unknown review JSON properties are rejected. Rejection reasons are trimmed and must contain 1–1000 characters; keep them free of credentials or document content.

Review JSON bodies are capped at 8 KiB before parsing, including chunked requests.

## Validation

- Each file is limited to **10 MiB**. A streaming ASGI limit caps the complete multipart request at 10 MiB plus 64 KiB before parsing/spooling, including requests without Content-Length. Multipart parsing starts after authentication and allows one file and one small field.
- Accept only `.pdf` with `application/pdf` or `.txt` with `text/plain`. Actual bytes are validated independently; a MIME header alone is insufficient.
- TXT must decode strictly as UTF-8 (an initial UTF-8 BOM is allowed). Empty/whitespace-only files, NUL and prohibited control characters, and obvious PDF/archive/executable signatures are rejected.
- PDF uses pinned pypdf in strict mode, with a bounded cross-reference stream table. It must have a valid header/trailer, catalog, and 1–1000 structurally valid pages. Corrupt, truncated, or encrypted PDFs are rejected. Validation does not extract/decompress page text or render the document.
- Filenames are metadata only. Use at most 199 ASCII letters/digits/dots/spaces/underscores/hyphens, starting with a letter/digit and ending in `.pdf` or `.txt`. Traversal, directory/drive separators, controls, repeated dots, and Windows reserved names are rejected. Rename files with unsupported names before upload.
- SHA-256 is computed from the exact original bytes, including any BOM. No content normalization is applied before hashing or Storage upload.

Structural validation is not antivirus scanning, a complete PDF renderer, or a guarantee that every embedded PDF feature is harmless. Original files remain untrusted and private. Production resource isolation/rate limits and any later text parser require their own controls.

## Lifecycle, authorization, and audit

An authenticated Student or Admin uploads a document as `pending / not_indexed`. The server generates a unique key `ingestions/<verified-user-uuid>/<document-uuid>.pdf|txt` and performs a non-upsert upload to the existing private `shieldrag-documents` bucket. It then registers metadata and a `document_uploaded` audit event in one database transaction.

Only an Admin can review. Approval downloads the canonical stored object through the trusted backend, computes SHA-256 again, and compares it with the original saved hash. Missing/tampered content cannot be approved. Confirmed integrity denials are persisted before the 409 response; see the independent audit operation below. Rejection requires no download, allowing an unsafe or missing file to be rejected.

`shield_review_document` rechecks the trusted Admin role, locks the document row, verifies pending state and the approval hash, updates reviewer/time, retains `not_indexed`, and inserts exactly one `document_approved` or `document_rejected` event in the same transaction. A failed audit insertion rolls back the state change. Competing reviews serialize on the row: one can commit and the other receives 409. Repeated transitions are not allowed. Approval integrity verification precedes this short transaction; the backend is the only application Storage writer, and no content-update endpoint exists. An operator possessing the server key remains a trusted privileged actor.

Pending/rejected files are retained privately. Existing chunk RLS and the search RPC still exclude pending/rejected records; Students still cannot retrieve restricted chunks. Task 03 creates no chunks. Approved documents remain not indexed until a separately authorized Task 04 workflow is implemented.

### Persistent integrity-denial audit (Task 03.1)

`shield_record_integrity_failure` is an additional server-role-only, SECURITY INVOKER RPC with a fixed empty search path. It rechecks the trusted Admin actor and document hash/path association, then appends an event without approving, rejecting, or changing any document fields. It commits independently: raising the approval's HTTP 409 inside the audit transaction would roll back the event and recreate the auditing gap.

Every event has server-controlled `event_type=document_integrity_failure`, `decision=deny`, the authenticated Admin reviewer as `user_id`, and the affected `document_id`. Its reason is selected from this fixed map:

| Confirmed condition | Persisted reason |
| --- | --- |
| SHA-256 mismatch | `SHA-256 mismatch detected` |
| Missing object (including Storage's recognized HTTP 400/404 NoSuchKey response) | `Stored object is missing` |
| Stored object exceeds the size bound | `Stored object exceeds size limit` |
| Missing saved SHA-256 | `Stored SHA-256 is missing` |
| Noncanonical stored object reference | `Stored object reference is invalid` |

General Storage/network/permission-service errors remain HTTP 503 and are not mislabeled as confirmed integrity failures. Event records contain no content, credentials, access tokens, observed hashes, Storage paths, or raw request data. The approval body stays `{}`; callers cannot supply audit fields or IDs. Neither Student nor Admin user JWTs gain direct event-write or RPC privileges.

The server generates one event UUID per approval attempt and reuses it for at most one internal retry after an uncertain/lost acknowledgement. The existing event primary key deduplicates the write, and the RPC rejects an ID rebound to another actor/document/failure. Separate HTTP attempts are separate security observations and intentionally produce separate events. A retry can confirm an already committed event without changing the document state.

If the write cannot be confirmed, the API returns **503**, keeps approval denied, and logs only document/reviewer/event UUIDs for investigation. A row may already exist if its acknowledgement was lost; the response does not claim it was recorded. Definite database failures are not automatically retried. The operation has no durable retry queue. The document remains pending absent another legitimate review; it never reverts another review's outcome.

**Task 04 must independently revalidate original-file SHA-256 immediately before any text extraction, chunking, or indexing.** It must not treat prior approval as a replacement for this new check. Those operations remain outside Task 03.1.

## Partial failures and errors

Storage and PostgreSQL are **not a distributed transaction**. On a definite metadata-registration failure (including a structured SQL/PostgREST RPC error), the backend attempts to delete its exact newly uploaded object, with one bounded retry. It never accepts a cleanup key from the request. Cleanup failure emits an operator-reconciliation log containing the document UUID and does not expose the object to clients. Transport/proxy failures and malformed/lost responses remain uncertain outcomes.

An RPC timeout or lost response may occur after commit. The backend checks the generated document ID and returns the committed metadata if its hash/path match. If completion remains uncertain, even when an immediate read finds no row, it preserves the object and returns 503: a delayed request could still commit. It logs the UUID for reconciliation. A failed Storage upload is also logged and never triggers blind deletion: it could represent an existing-object collision or a lost response, and this operation did not confirm object creation. Operators must let in-flight operations settle and inspect exact metadata/keys before removing any orphan. Blindly deleting a possibly committed document's object is unsafe. Process crashes also require reconciliation. Automatic durable orphan reconciliation and client idempotency keys are deferred.

Errors use the existing sanitized `{detail: ...}` envelope: 400 malformed/excess multipart parts, 401 invalid/missing JWT, 403 denied review, 404 missing/hidden metadata, 409 state/integrity conflict, 413 size limit, 415 unsupported content type, 422 invalid content/name/fields, and 503 configuration/upstream/uncertain completion. No upstream error body or server key is returned or logged.

## Testing

Run the mocked suite from `backend/`:

```powershell
.venv/Scripts/python -m pip install -r requirements.lock
.venv/Scripts/python -m pytest -q -m 'not integration' -p no:cacheprovider
```

The HTTPX transport fake covers validation, exact bytes/hash/key/state, metadata permissions, Admin review, tampering, conflict propagation, definite-failure cleanup, failed cleanup, lost commits, and unresolved outcomes. It is not evidence that cloud Storage worked.

For live checks, use the synthetic fixture setup in [testing](testing.md), configure the server key privately, and add:

```powershell
$env:SHIELDRAG_INTEGRATION = '1'
$env:SHIELDRAG_LIVE_FIXTURES = '1'
$env:SHIELDRAG_INGESTION = '1'
$env:SHIELDRAG_FIXTURE_MANIFEST = '.integration/<fresh-run>/manifest.json'
.venv/Scripts/python -m pytest -q -p no:cacheprovider
```

The ingestion tests create only uniquely named uploads owned by the synthetic accounts. Teardown checks uploader/run/name/key/chunk/audit references, deletes exact objects through the Storage API, then removes their audit/metadata rows, including the new integrity events. It never deletes Storage records through SQL. An ignored ingestion journal remains if teardown fails; resolve it before applying the original guarded account cleanup. The separate `tests/ingestion_rollback.sql` and `tests/integrity_audit_rollback.sql` verify real RPC grants, trusted actors/document association, retry deduplication, write denial, state preservation, and audit records entirely inside rolled-back operator transactions. Live tests also forward real Supabase calls while deliberately dropping one successful audit acknowledgement, then verify one persisted event after the backend retry. See [verification](verification.md) for actual results and skips.
