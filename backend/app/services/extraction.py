import asyncio
import json
import os
import subprocess
import sys

from fastapi import HTTPException

from app.core.config import BACKEND_ROOT, Settings


async def extract_pages(data: bytes, extension: str, settings: Settings) -> list[dict]:
    # The parser receives no application credentials and never follows links/scripts.
    environment = {k: v for k, v in os.environ.items() if k.upper() in (
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL')}
    environment['PYTHONPATH'] = str(BACKEND_ROOT)
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'app.services.extract_worker',
            extension, str(settings.rag_max_pdf_pages), str(settings.rag_max_text_chars),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=environment, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
    except OSError:
        raise HTTPException(503, 'Document extraction worker unavailable') from None
    try:
        output, _ = await asyncio.wait_for(process.communicate(data), settings.rag_extraction_timeout)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode != 0 or len(output) > settings.rag_max_text_chars * 6 + 20000:
        raise HTTPException(422, 'Document extraction failed or exceeded limits')
    try:
        result = json.loads(output)
        pages = result['pages']
        if not isinstance(pages, list) or any(not isinstance(p['text'], str) for p in pages):
            raise ValueError('Malformed extraction')
        return pages
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, 'Document extraction failed') from None
