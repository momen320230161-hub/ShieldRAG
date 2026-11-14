import hashlib
import hmac
import logging
from uuid import UUID, uuid4

import anyio
from fastapi import HTTPException

from app.core.authentication import Principal
from app.db.document_store import DocumentStore, object_key
from app.db.supabase_client import SupabaseGateway
from app.services.file_validation import ValidatedFile

logger = logging.getLogger(__name__)
METADATA_FIELDS = ('id,uploaded_by,original_name,visibility,sha256,review_status,index_status,'
                   'reviewed_by,reviewed_at,created_at')


async def read_document(gateway: SupabaseGateway, principal: Principal, document_id: UUID,
                        *, for_review=False):
    fields = METADATA_FIELDS + (',storage_path' if for_review else '')
    rows = await gateway.get('/rest/v1/documents', principal.token,
                             {'id': f'eq.{document_id}', 'select': fields, 'limit': '1'})
    if not rows:
        raise HTTPException(404, 'Document not found')
    document = rows[0]
    allowed = (principal.user.role == 'admin' or document.get('uploaded_by') == str(principal.user.id)
               or (document.get('review_status') == 'approved' and document.get('visibility') == 'public'))
    if document.get('id') != str(document_id) or not allowed:
        raise HTTPException(404, 'Document not found')
    return document


async def compensate_upload(store: DocumentStore, principal: Principal, document_id: UUID, extension: str):
    for _ in range(2):
        try:
            await store.remove_upload(principal, document_id, extension)
            return
        except HTTPException:
            continue
    logger.error('Storage compensation requires operator reconciliation; document_id=%s', document_id)


async def upload_document(store: DocumentStore, principal: Principal, file: ValidatedFile,
                          data: bytes, visibility: str):
    document_id = uuid4()
    sha256 = hashlib.sha256(data).hexdigest()
    # Fail before acquiring external resources if writes are not configured.
    store.ensure_available(principal)
    with anyio.CancelScope(shield=True):
        try:
            await store.upload(principal, document_id, file.extension, file.content_type, data)
        except HTTPException as error:
            # Failure may mean an existing-object collision or a lost response.
            # Do not delete an object whose creation this operation did not confirm.
            if error.status_code == 503:
                logger.error('Storage upload outcome uncertain; operator reconciliation required; document_id=%s', document_id)
            raise
        try:
            return await store.register(principal, document_id, file.original_name,
                                         file.extension, sha256, visibility)
        except HTTPException as error:
            if error.status_code == 503 and not getattr(error, 'definite_failure', False):
                try:
                    committed = await store.upload_outcome(principal, document_id)
                except HTTPException:
                    # Do not delete a possibly committed document's only object.
                    logger.error('Upload outcome unknown; operator reconciliation required; document_id=%s', document_id)
                    raise error from None
                if committed is not None:
                    if (committed.get('sha256') == sha256 and committed.get('storage_path') ==
                            object_key(principal.user.id, document_id, file.extension)):
                        return committed
                    logger.error('Upload outcome conflict; operator reconciliation required; document_id=%s', document_id)
                    raise error from None
                # An absent row does not prove a timed-out RPC cannot commit later.
                logger.error('Upload completion uncertain; operator reconciliation required; document_id=%s', document_id)
                raise error from None
            await compensate_upload(store, principal, document_id, file.extension)
            raise


async def review_document(gateway: SupabaseGateway, store: DocumentStore, principal: Principal,
                          document_id: UUID, decision: str, reason: str | None = None):
    if principal.user.role != 'admin':
        raise HTTPException(403, 'Admin role required')
    document = await read_document(gateway, principal, document_id, for_review=True)
    if document['review_status'] != 'pending':
        raise HTTPException(409, 'Only pending documents can be reviewed')
    verified_hash = None
    if decision == 'approved':
        data = await store.download_for_review(principal, document)
        verified_hash = hashlib.sha256(data).hexdigest()
        if not document['sha256'] or not hmac.compare_digest(verified_hash, document['sha256']):
            logger.warning('Document integrity check denied; document_id=%s reviewer_id=%s',
                           document_id, principal.user.id)
            raise HTTPException(409, 'Stored document integrity check failed')
    return await store.review(principal, document_id, decision, verified_hash, reason)
