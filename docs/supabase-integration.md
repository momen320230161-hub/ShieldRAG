# Supabase integration

Inspected project: `ShieldRAG`, ref `bnehmoxpzycxnsdxxfxc`, on 2026-11-14. The repository was empty. The existing project contains `profiles`, `documents`, `document_chunks`, `chat_sessions`, `chat_messages`, `security_events`, and `evaluation_runs`, each with RLS enabled; embedding type is `extensions.vector(768)`; bucket `shieldrag-documents` is private.

The two remote migration records and their SQL statements were exported from `supabase_migrations.schema_migrations` into `supabase/migrations/` with their original versions and names:

- `20261114110240_shieldrag_initial_secure_schema.sql`
- `20261114110308_shieldrag_foreign_key_indexes.sql`

These files record already-applied migrations. Do not replay them against the existing project, reset its database, or repair its migration history. The application does not apply migrations at startup. No schema, policy, bucket, or migration changes were made to the live project for this task.

The application uses an HTTPX REST adapter instead of a stateful Supabase SDK client. Each request supplies the publishable API key and the original user's access token. Credentials are never stored as shared mutable HTTP client authorization headers. Redirect following and ambient proxy configuration are disabled to avoid forwarding credentials to another origin. HTTPS uses normal certificate verification and a ten-second upstream timeout.

Authentication calls `GET /auth/v1/user` on the configured project. Supabase Auth performs JWT verification, including signature and expiration; this works with both legacy signing secrets and asymmetric signing keys without copying signing secrets to the backend. After successful validation, the application reads `profiles` with the same token and an exact authenticated-id filter. It does not trust HTTP role fields or metadata.

Data reads use PostgREST `/rest/v1/profiles`, `/documents`, and `/security_events`. Future retrieval must use `match_shield_chunks` with the user's token and must retain its approval/visibility conditions. The current foundation makes no Gemini calls.

Existing RLS permits uploaders to read their own pending/rejected document metadata and Admins to review all metadata. The backend's retrieval catalog intentionally applies a stricter approved-only filter. Chunk RLS and the security-invoker RPC exclude pending/rejected chunks even for Admins. Students cannot retrieve restricted chunks, including chunks of documents they uploaded.

Profile creation assigns `student` in a private trigger; the role lookup uses a private function with fixed search path. Existing write privileges have no corresponding RLS write policies, so row writes are denied. No API role mutation path is provided. Database administration credentials remain privileged and must be restricted to operators. Storage has no user object policies yet, so uploads/downloads remain unavailable; bucket privacy alone is not a completed upload workflow.

Reference documentation: [server-side access-token validation](https://supabase.com/docs/reference/python/auth-getuser), [JWTs](https://supabase.com/docs/guides/auth/jwts), [API keys](https://supabase.com/docs/guides/api/api-keys).

Task 02.1 adds [reproducible full live verification](testing.md) using isolated synthetic accounts and documents. Tests obtain real JWTs from the public password sign-in endpoint and verify both FastAPI and direct RLS/RPC behavior. Setup/cleanup SQL is operator-only, does not change schemas or migrations, and never reads production-like document content. Temporary accounts and synthetic content are committed for cross-connection HTTP testing and then safely removed. Current error classification follows documented [Auth error codes](https://supabase.com/docs/guides/auth/debugging/error-codes).
