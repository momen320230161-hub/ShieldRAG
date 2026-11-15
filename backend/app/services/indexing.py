import asyncio
import hashlib
import hmac
import logging
from dataclasses import asdict
from uuid import UUID, uuid4

import anyio
from fastapi import HTTPException

from app.db.document_store import DocumentIntegrityError
from app.services.audit import record_integrity_failure
from app.services.chunking import chunk_pages, configuration_hash
from app.services.documents import read_document
from app.services.extraction import extract_pages

logger = logging.getLogger(__name__)


async def verified_bytes(store, principal, document):
    try:
        data = await store.download_for_review(principal, document)
    except DocumentIntegrityError as error:
        await record_integrity_failure(store, principal, document, error.failure)
        raise
    observed = hashlib.sha256(data).hexdigest()
    if not document.get('sha256') or not hmac.compare_digest(observed, document['sha256']):
        await record_integrity_failure(store, principal, document,
            'sha256_mismatch' if document.get('sha256') else 'stored_hash_missing', observed)
        raise HTTPException(409, 'Stored document integrity check failed')
    return data


async def index_document(gateway, store, rag_store, gemini, principal, document_id: UUID, settings):
    if principal.user.role != 'admin':
        raise HTTPException(403, 'Admin role required')
    document = await read_document(gateway, principal, document_id, for_review=True)
    if document['review_status'] != 'approved':
        raise HTTPException(409, 'Only approved documents can be indexed')
    job = uuid4()
    state = await rag_store.begin(principal, document_id, job, document['sha256'],
                                   settings.gemini_embedding_model, configuration_hash(settings))
    cached = state.get('index_status') == 'indexed'
    try:
        async with asyncio.timeout(settings.rag_index_timeout):
            data = await verified_bytes(store, principal, document)
            if cached:
                rows = await gateway.get('/rest/v1/document_chunks', principal.token,
                    {'document_id': f'eq.{document_id}', 'select': 'id', 'limit': '256'})
                return result(document_id, settings, len(rows), True)
            pages = await extract_pages(data, document['storage_path'].rsplit('.', 1)[-1], settings)
            chunks = chunk_pages(pages, settings)
            vectors = await gemini.embed([c.content for c in chunks], 'RETRIEVAL_DOCUMENT')
            if len(vectors) != len(chunks):
                raise HTTPException(503, 'Invalid embedding response')
            # Recheck the original immediately before publishing the completed set.
            await verified_bytes(store, principal, document)
            published = await rag_store.publish(principal, document_id, job, document['sha256'],
                [{**asdict(chunk), 'embedding': vector} for chunk, vector in zip(chunks, vectors)])
            if published.get('index_status') != 'indexed':
                raise HTTPException(503, 'Index publication was not confirmed')
            logger.info('Document indexed; document_id=%s chunks=%s', document_id, len(chunks))
            return result(document_id, settings, len(chunks), False)
    except BaseException as error:
        # Cleanup is shielded from request cancellation. Lease expiry handles process crashes.
        with anyio.CancelScope(shield=True):
            try:
                await rag_store.fail(principal, document_id, job)
            except HTTPException:
                logger.error('Index reconciliation required; document_id=%s', document_id)
        if isinstance(error, TimeoutError):
            raise HTTPException(503, 'Document indexing exceeded its time limit') from None
        raise


def result(document_id, settings, count, cached):
    return {'document_id': document_id, 'index_status': 'indexed', 'chunk_count': count,
            'embedding_model': settings.gemini_embedding_model, 'dimensions': 768, 'cached': cached}
