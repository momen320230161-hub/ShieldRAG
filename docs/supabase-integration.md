# Supabase integration

Inspected project: `ShieldRAG`, ref `bnehmoxpzycxnsdxxfxc`, on 2026-11-14. The repository was empty. The existing project contains `profiles`, `documents`, `document_chunks`, `chat_sessions`, `chat_messages`, `security_events`, and `evaluation_runs`, each with RLS enabled; embedding type is `extensions.vector(768)`; bucket `shieldrag-documents` is private.

The two remote migration records and their SQL statements were exported from `supabase_migrations.schema_migrations` into `supabase/migrations/` with their original versions and names:

- `20261114110240_shieldrag_initial_secure_schema.sql`
- `20261114110308_shieldrag_foreign_key_indexes.sql`

These files record already-applied migrations. Do not replay them against the existing project, reset its database, or repair its migration history. The application does not apply migrations at startup. Task 02 made no schema, policy, bucket, or migration changes; Task 03's additive write-function migration is described below.

The application uses an HTTPX REST adapter instead of a stateful Supabase SDK client. Each request supplies the publishable API key and the original user's access token. Credentials are never stored as shared mutable HTTP client authorization headers. Redirect following and ambient proxy configuration are disabled to avoid forwarding credentials to another origin. HTTPS uses normal certificate verification and a ten-second upstream timeout.

Authentication calls `GET /auth/v1/user` on the configured project. Supabase Auth performs JWT verification, including signature and expiration; this works with both legacy signing secrets and asymmetric signing keys without copying signing secrets to the backend. After successful validation, the application reads `profiles` with the same token and an exact authenticated-id filter. It does not trust HTTP role fields or metadata.

Data reads use PostgREST `/rest/v1/profiles`, `/documents`, `/document_chunks`, and `/security_events`. Task 04 retrieval uses `match_shield_chunks` with the user's token and retains approval/visibility conditions plus verified indexed/hash/consent gates. [Baseline RAG](rag.md) documents external Gemini calls.

Existing RLS permits uploaders to read their own pending/rejected document metadata and Admins to review all metadata. The backend's retrieval catalog intentionally applies a stricter approved-only filter. Chunk RLS and the security-invoker RPC exclude pending/rejected chunks even for Admins. Students cannot retrieve restricted chunks, including chunks of documents they uploaded.

Profile creation assigns `student` in a private trigger; the role lookup uses a private function with fixed search path. Existing authenticated write privileges have no corresponding RLS write policies, so direct user row writes remain denied. No API role mutation path is provided. Database administration credentials remain privileged and must be restricted to operators. Storage has no user object policies, so direct user object access remains unavailable. Task 03's authorized Python backend handles private upload and approval-time download.

Reference documentation: [server-side access-token validation](https://supabase.com/docs/reference/python/auth-getuser), [JWTs](https://supabase.com/docs/guides/auth/jwts), [API keys](https://supabase.com/docs/guides/api/api-keys).

Task 02.1 adds [reproducible full live verification](testing.md) using isolated synthetic accounts and documents. Tests obtain real JWTs from the public password sign-in endpoint and verify both FastAPI and direct RLS/RPC behavior. Setup/cleanup SQL is operator-only, does not change schemas or migrations, and never reads production-like document content. Temporary accounts and synthetic content are committed for cross-connection HTTP testing and then safely removed. Current error classification follows documented [Auth error codes](https://supabase.com/docs/guides/auth/debugging/error-codes).

Task 03 adds the forward migration `20261114141719_shieldrag_secure_document_ingestion`, already applied to the existing project. It defines only `shield_register_document` and `shield_review_document`, both fixed-search-path SECURITY INVOKER functions executable only by service_role. They recheck trusted roles and atomically write their document/audit changes. No table, bucket, or RLS policy is reset, recreated, or weakened. Python authenticates/authorizes before using a modern server secret for these RPCs and private Storage; user reads continue to use publishable-key + bearer JWT. No user Storage policy or public URL is introduced.


## Task 04 atomic indexing

Forward migration `20261115143019_shieldrag_atomic_baseline_rag.sql` adds document index lease/model/config/hash/consent metadata and service-only `shield_begin_index`, `shield_publish_index`, `shield_fail_index`. They are SECURITY INVOKER with fixed empty search paths; anon/authenticated cannot execute them. Publication replaces all chunks and commits indexed status/audit together. The existing `match_shield_chunks(vector,integer)` signature and return shape are retained, with stronger verified-index predicates in both the RPC and chunk SELECT policy. No existing table is recreated or database reset. See [RAG architecture](rag.md) for concurrency, failure recovery, external-transfer authorization and stateless chat rationale.

Task 05 adds forward migration `20261115202657_shieldrag_security_agent_audit.sql`, with one service-only SECURITY INVOKER audit RPC. It writes fixed stages/reasons/policy version to existing `security_events`, checks registered actors and authorized optional document association, and deduplicates trusted internal event UUIDs. No table or RLS policy changes. Both ordinary Student and Admin JWTs remain unable to execute this RPC directly. Secure RAG retrieval continues using the caller JWT; the server key is used only for the narrow audit write. See [Security Agent](security-agent.md).
