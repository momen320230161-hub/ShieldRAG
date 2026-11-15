# ShieldRAG

Academic secure RAG backend. Python 3.12+, FastAPI, Gemini and the existing Supabase Cloud project. Backend only; no frontend or AI Security Agent.

Start with [backend setup](docs/backend-setup.md), [API contracts](docs/api-contracts.md), [Supabase integration](docs/supabase-integration.md), [security architecture](docs/security.md), and [testing](docs/testing.md).

Task 02.1 adds [full live authentication/RLS verification](docs/testing.md), [recorded results](docs/verification.md), and the [branch/PR workflow](docs/git-workflow.md).

Task 03 adds [secure document ingestion and Admin review](docs/document-ingestion.md), with private Storage, original-byte SHA-256, pending metadata, and transactional review/audit writes. Task 03.1 persists integrity-denial events with retry deduplication and fail-closed audit handling. Task 04 adds [baseline RAG](docs/rag.md): approved PDF/TXT indexing, normalized 768-dimensional Gemini embeddings, caller-scoped pgvector retrieval, and grounded answers with validated citations. See the [verification report](docs/verification.md) for executed checks and operational limits.
