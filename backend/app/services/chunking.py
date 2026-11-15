import hashlib
import json
import re
from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import Settings


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    page_number: int | None
    content: str


def configuration_hash(settings: Settings) -> str:
    config = {'version': 2, 'words': settings.rag_chunk_words, 'overlap': settings.rag_overlap_words,
              'max_bytes': settings.rag_chunk_max_bytes, 'embedding_model': settings.gemini_embedding_model,
              'dimensions': 768, 'normalization': 'l2', 'provenance': 'one-page-per-chunk'}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def chunk_pages(pages: list[dict], settings: Settings) -> list[Chunk]:
    if sum(len(page['text']) for page in pages) > settings.rag_max_text_chars:
        raise HTTPException(422, 'Extracted text exceeds limit')
    chunks, seen = [], set()
    for page in pages:
        words = re.findall(r'\S+', page['text'])
        start = 0
        while start < len(words):
            end, size = start, 0
            while end < len(words) and end - start < settings.rag_chunk_words:
                added = len(words[end].encode('utf-8')) + (1 if end > start else 0)
                if size + added > settings.rag_chunk_max_bytes:
                    break
                size += added
                end += 1
            if end == start:
                raise HTTPException(422, 'A text unit exceeds the embedding input bound')
            content = ' '.join(words[start:end])
            # A source occurrence is identified by its page and word interval.
            # Equal text at another location is legitimate content, including TXT.
            occurrence = (page['page'], start, end, content)
            if occurrence not in seen:
                seen.add(occurrence)
                chunks.append(Chunk(len(chunks), page['page'], content))
                if len(chunks) > settings.rag_max_chunks:
                    raise HTTPException(422, 'Document produces too many chunks')
            if end == len(words):
                break
            # Guarantee forward progress even for short byte-limited windows.
            start = max(start + 1, end - min(settings.rag_overlap_words, (end - start) // 3))
    if not chunks:
        raise HTTPException(422, 'Document has no extractable text; OCR is not supported')
    return chunks
