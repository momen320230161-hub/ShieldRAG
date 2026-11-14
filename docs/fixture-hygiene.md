# Generated integration fixture cleanup

The `1913fe1` commit on `main` accidentally tracked four generated files:
`backend/.integration/{final,live}/{setup,cleanup}.sql`.
The repair merges `main` into `feat/backend-hardening-verification`, removes
these files from the Git index, and explicitly ignores `/backend/.integration/`.
The generator in `backend/scripts/integration_fixtures.py`, guarded cleanup
tooling, tests, migrations, and all existing history are preserved. Existing
local fixture files remain available for any necessary operator cleanup.
CI rejects tracked files under this generated directory, even if force-added.

## Sensitive-content review

Both setup files contain two synthetic `@example.invalid` accounts each,
random user/run/document/chunk UUIDs, bcrypt password hashes, synthetic text,
and synthetic vectors. The cleanup files contain matching identifiers and
guarded deletion statements. No plaintext passwords, JWTs, API keys, database
connection strings, private keys, or real document contents were found in the
four reviewed files. The generator creates passwords with
`secrets.token_urlsafe(32)` and keeps them in a separate local manifest;
no manifest was tracked in the repository history inspected for this repair.

The hashes and identifiers remain exposed in existing Git history. Removing
tracked files does not erase that exposure. No history rewrite or force-push
is part of this repair. Do not reuse these fixtures or their credentials.
The earlier verification report records successful cleanup, but this repair
does not independently verify current cloud rows or repeat live provisioning.
If an operator finds any exposed fixture account still active, use the
existing guarded cleanup after checking its markers and references. Keep the
private manifest and cleanup SQL until removal is confirmed; never upload them.

## Validation scope

Run the mocked suite with Python 3.12 and `backend/requirements.lock`, verify
the Git index contains no files under `backend/.integration/`, and check that
both SQL and manifest paths are ignored. Default GitHub CI runs the mocked
suite and the tracked-fixture guard. Live Supabase verification remains an
opt-in operator procedure documented in [testing.md](testing.md); earlier live
results are historical evidence, not a new live run for this cleanup.
