# ShieldRAG

ShieldRAG is a secure academic retrieval application. The FastAPI backend uses Supabase and Gemini. The React frontend provides account sign-in and separate Student and Admin workspaces.

Start with [backend setup](docs/backend-setup.md), [API contracts](docs/api-contracts.md), [Supabase integration](docs/supabase-integration.md), [security architecture](docs/security.md), and [testing](docs/testing.md).

For local browser development, run FastAPI in one terminal and Vite in another. Use an existing provisioned Student or Admin account. [Frontend setup](frontend/README.md) · [Architecture](docs/frontend-architecture.md) · [Authentication](docs/frontend-authentication.md).

Task 02.1 adds [full live authentication/RLS verification](docs/testing.md), [recorded results](docs/verification.md), and the [branch/PR workflow](docs/git-workflow.md).

Task 03 adds [secure document ingestion and Admin review](docs/document-ingestion.md), with private Storage, original-byte SHA-256, pending metadata, and transactional review/audit writes. Task 03.1 persists integrity-denial events with retry deduplication and fail-closed audit handling. Task 04 adds [baseline RAG](docs/rag.md): approved PDF/TXT indexing, normalized 768-dimensional Gemini embeddings, caller-scoped pgvector retrieval, and grounded answers with validated citations. See the [verification report](docs/verification.md) for executed checks and operational limits.

Task 05 adds a [Security Agent and secure RAG endpoint](docs/security-agent.md), preserving the baseline for comparison. A trained scikit-learn classifier, deterministic rules, context/output checks and trusted audit writes complement existing authorization. Measured false positives, residual attacks and synthetic-only evaluation limits are reported explicitly; this is a reviewable experimental baseline, not production-grade prompt-injection prevention.
