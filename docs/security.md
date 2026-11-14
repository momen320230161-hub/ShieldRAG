# Security architecture

Requests cross three boundaries: HTTP bearer authentication, trusted profile RBAC, and Supabase RLS. None of the read routes uses a secret or service-role key. A role is refreshed from trusted `profiles` data on each request, avoiding authorization based on stale JWT metadata. User-editable metadata, HTTP headers such as `X-Role`, and query parameters cannot promote an account.

`require_admin` is reusable for future review/evaluation operations. It is tested using a test-only route; that route is absent from the production application. The current document list is a retrieval catalog and returns only approved records. `can_retrieve_document` is a defense-in-depth guard; future generation code must call the user-scoped search RPC and keep approved-only checks. There is no generation pipeline to bypass today.

Security event reads follow existing RLS: Students see only their own events, Admins see all, and rows without a user are Admin-only. Both the query and response filtering enforce this boundary. There is no event-writing endpoint. Future server-created audit reasons must contain only safe summaries.

Invalid tokens return 401, absent/unrecognized profiles return 403, and upstream failures return sanitized 503 responses. Keys and bearer tokens are omitted from response models and principal representations. No authentication bypass or development token feature exists. Supabase validates the JWT remotely; unit tests mock that verifier's results rather than pretending to prove cryptography. Live negative-token tests exercise the real verifier.

RLS tests in `backend/tests/rls_rollback.sql` create synthetic fixtures inside a rolled-back transaction. They test effective authenticated roles, forged metadata, role/update denial, security event ownership, approved-only chunks and the RPC. This SQL must run through an authorized operator connection. It does not test stolen-session revocation or external network controls. Access tokens remain valid according to Supabase session and expiration behavior; instant revocation on every endpoint is not promised.

Before enabling privileged server writes, enforce Admin authorization before acquiring privileged access, validate transition ownership/state, and implement transactional audit records. A nonempty `SUPABASE_SECRET_KEY` currently grants the application no extra capability because no code reads it for requests.

The live Supabase security advisor reported no findings during this task. This is one verification signal and does not replace ongoing dependency updates, deployment hardening, or future pipeline security evaluation.
