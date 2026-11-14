"""Verify cleanup orchestration without a network or privileged connection."""
from types import SimpleNamespace

import pytest

from scripts import verify_live


@pytest.mark.parametrize('setup_ok,test_exit,cleanup_ok,expected', [
    (True, 0, True, 0), (True, 1, True, 1), (False, 0, True, 1),
    (True, 0, False, 1),
])
def test_runner_always_cleans_up_and_preserves_failures(
        monkeypatch, tmp_path, setup_ok, test_exit, cleanup_ok, expected):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text('private synthetic credentials', encoding='utf-8')
    applied = []

    def apply(path):
        applied.append(path.name)
        return setup_ok if path.name == 'setup.sql' else cleanup_ok

    monkeypatch.setattr(verify_live.shutil, 'which', lambda name: 'psql')
    monkeypatch.setattr(verify_live, 'prepare', lambda: tmp_path)
    monkeypatch.setattr(verify_live, 'apply_sql', apply)
    monkeypatch.setattr(verify_live.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=test_exit))
    with pytest.raises(SystemExit) as outcome:
        verify_live.main()
    actual = outcome.value.code
    assert (actual if isinstance(actual, int) else 1) == expected
    assert applied == ['setup.sql', 'cleanup.sql']
    assert manifest.exists() == (not cleanup_ok)


def test_runner_does_not_provision_without_psql(monkeypatch):
    monkeypatch.setattr(verify_live.shutil, 'which', lambda name: None)

    def unexpected_prepare():
        pytest.fail('Provisioning must not run when psql is unavailable')

    monkeypatch.setattr(verify_live, 'prepare', unexpected_prepare)
    with pytest.raises(SystemExit, match='psql is required'):
        verify_live.main()
