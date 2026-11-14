# Task 02 verification — 2026-11-14

- Python 3.12.10; installed dependencies consistent (`pip check`).
- Complete pytest run: **35 passed, 2 skipped**. This includes 32 mocked tests and three live HTTP tests: Supabase Auth health, real forged-JWT rejection through FastAPI, and anonymous table access rejected with PostgreSQL permission code `42501`.
- Live synthetic RLS transaction: passed; all fixtures rolled back. Verified Student/Admin chunk access, pending/rejected exclusion, RPC visibility guards, denied Student role/approval mutations, and security-event ownership.
- Real Uvicorn startup and local HTTP request: `/health` returned `200 {"status":"ok"}`; temporary server stopped.
- All seven existing public tables have RLS enabled; embedding type is `vector(768)`; document bucket is private; two existing migration statement arrays exported with original version/name.
- Supabase security advisor: no findings.
- One upstream test-client deprecation warning (`anyio.abc.BlockingPortal`) remains; it does not affect the assertions.

**Remaining acceptance blocker:** positive authenticated HTTP tests for both Student and Admin were skipped because no synthetic account access tokens were supplied. Live database role tests do not replace proof of successful real user sign-in/JWT acceptance. Supply `SHIELDRAG_STUDENT_TOKEN` and `SHIELDRAG_ADMIN_TOKEN` and rerun the opt-in integration suite before declaring full acceptance complete.

The initial Data API root probe returned `401 Secret API key required`; the probe was corrected to check the user-accessible table endpoint's anonymous denial instead. The backend continues to use only the publishable key and each user's bearer token.

No live schema/migration/policy changes, persistent test fixtures, frontend, full RAG, Gemini calls, or AI Security Agent were introduced. Upload, review, chat, and evaluation routes remain documented future contracts.
