"""One-command SQL setup -> real HTTP tests -> guarded cleanup using psql.

Use standard PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD or PGSERVICE environment
configuration for an authorized operator connection. No secrets go in argv.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.integration_fixtures import main as prepare


def apply_sql(path: Path) -> bool:
    result = subprocess.run(['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1',
                             '-f', str(path)], capture_output=True, text=True)
    # SQL diagnostics can echo statements. Keep all upstream text out of logs.
    return result.returncode == 0


def main():
    if not shutil.which('psql'):
        raise SystemExit('psql is required; alternatively use the documented SQL-operator workflow')
    # Reuse the same preparation CLI, including its output-directory safety check.
    directory = prepare()
    result = 1
    try:
        if not apply_sql(directory / 'setup.sql'):
            raise SystemExit('Fixture setup failed; check the private SQL using an authorized connection')
        environment = {**os.environ, 'SHIELDRAG_INTEGRATION': '1', 'SHIELDRAG_LIVE_FIXTURES': '1',
                       'SHIELDRAG_FIXTURE_MANIFEST': str(directory / 'manifest.json')}
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                                env=environment).returncode
    finally:
        if not apply_sql(directory / 'cleanup.sql'):
            raise SystemExit('Fixture cleanup failed: retain the private manifest and run cleanup.sql')
        print('Guarded fixture cleanup completed.')
        # Preserve scripts as evidence; erase local passwords after database removal.
        (directory / 'manifest.json').unlink()
    raise SystemExit(result)


if __name__ == '__main__':
    main()
