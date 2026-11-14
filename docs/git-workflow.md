# Repository workflow

The original history is preserved:

- `66cf863` — empty bootstrap commit.
- `66aba0e` — Task 02 backend implementation.

Task 02.1 established remote `main` at existing implementation commit `66aba0e` with a fast-forward of the local bootstrap branch. The original `feat/backend-supabase-integration` branch remains intact. Hardening changes are delivered on `feat/backend-hardening-verification` in a PR targeting `main`. This makes the existing implementation available as the PR base while keeping review fixes pending explicit review; nothing is automatically merged.

Subsequent work starts from an up-to-date `main`, uses a dedicated feature branch, and opens a PR. Do not force-push, delete existing branches, rewrite commits, reset Supabase, or replay already-applied migrations. Update `main` with reviewed changes through the repository's normal PR process.
