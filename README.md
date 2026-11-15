# ShieldRAG

Academic secure RAG backend foundation. Python 3.12+, FastAPI and the existing Supabase Cloud project. No frontend, generation pipeline, or AI Security Agent is implemented in this task.

Start with [backend setup](docs/backend-setup.md), [API contracts](docs/api-contracts.md), [Supabase integration](docs/supabase-integration.md), [security architecture](docs/security.md), and [testing](docs/testing.md).

Task 02.1 adds [full live authentication/RLS verification](docs/testing.md), [recorded results](docs/verification.md), and the [branch/PR workflow](docs/git-workflow.md).

Task 03 adds [secure document ingestion and Admin review](docs/document-ingestion.md), with private Storage, original-byte SHA-256, pending metadata, and transactional review/audit writes. Task 03.1 persists integrity-denial events with retry deduplication and fail-closed audit handling. The [verification report](docs/verification.md) records 158 passing tests, including real cloud integrity auditing, and the remaining operational limits.
