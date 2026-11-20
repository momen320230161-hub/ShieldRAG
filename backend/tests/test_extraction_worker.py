"""Exercise subprocess I/O and cleanup without external services."""
import asyncio
import sys

import pytest
from fastapi import HTTPException

from app.services.extract_worker import MAX_BYTES
from app.services.extraction import extract_pages
from test_rag import settings


@pytest.fixture
def track_workers(monkeypatch):
    start = asyncio.create_subprocess_exec
    workers = []

    def track(child_code=None):
        async def observe(*args, **kwargs):
            if child_code is not None:
                args = (sys.executable, '-c', child_code)
            process = await start(*args, **kwargs)
            workers.append(process)
            return process

        monkeypatch.setattr(asyncio, 'create_subprocess_exec', observe)
        return workers

    return track


def test_repeated_and_concurrent_workers_exit_without_files(track_workers, monkeypatch, tmp_path):
    workers = track_workers()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TEMP', str(tmp_path))
    monkeypatch.setenv('TMP', str(tmp_path))
    config = settings()

    async def run():
        first = await extract_pages(b'First synthetic input.', 'txt', config)
        second, third = await asyncio.gather(
            extract_pages(b'Second synthetic input.', 'txt', config),
            extract_pages(b'Third synthetic input.', 'txt', config),
        )
        return first, second, third

    results = asyncio.run(run())
    assert results == tuple([{'page': None, 'text': f'{order} synthetic input.'}]
                            for order in ('First', 'Second', 'Third'))
    assert [worker.returncode for worker in workers] == [0, 0, 0]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('extension,data', [
    ('txt', b'\xff'),
    ('pdf', b'invalid PDF'),
    ('txt', b'x' * (MAX_BYTES + 1)),
], ids=['invalid-utf8', 'invalid-pdf', 'oversized'])
def test_real_worker_rejects_invalid_or_oversized_input(track_workers, extension, data):
    workers = track_workers()
    with pytest.raises(HTTPException) as error:
        asyncio.run(extract_pages(data, extension, settings()))

    assert error.value.status_code == 422
    assert error.value.detail == 'Document extraction failed or exceeded limits'
    assert [worker.returncode for worker in workers] == [2]


def test_extraction_timeout_reaps_child(track_workers):
    workers = track_workers('import time; time.sleep(10)')
    with pytest.raises(TimeoutError):
        asyncio.run(extract_pages(b'Synthetic input.', 'txt', settings(rag_extraction_timeout=1)))

    assert len(workers) == 1
    assert workers[0].returncode not in (None, 0)


def test_crashed_child_is_reaped_and_diagnostics_are_redacted(track_workers):
    workers = track_workers(
        "import os, sys; print('private test diagnostic', file=sys.stderr, flush=True); os._exit(17)"
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(extract_pages(b'Synthetic input.', 'txt', settings()))

    assert error.value.status_code == 422
    assert error.value.detail == 'Document extraction failed or exceeded limits'
    assert [worker.returncode for worker in workers] == [17]
