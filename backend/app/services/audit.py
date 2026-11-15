import logging
from uuid import uuid4

import anyio
from fastapi import HTTPException

from app.core.authentication import Principal
from app.db.document_store import DocumentStore
from app.db.supabase_client import SupabaseGateway

logger = logging.getLogger(__name__)


async def record_integrity_failure(store: DocumentStore, principal: Principal, document: dict,
                                    failure: str, observed_sha256: str | None = None):
    """Confirm an independent audit commit before returning the integrity denial.

    One server UUID per review attempt is reused if its acknowledgement is lost.
    The RPC deduplicates using the existing security_events primary key.
    """
    event_id = uuid4()
    with anyio.CancelScope(shield=True):
        for attempt in range(2):
            try:
                await store.record_integrity_failure(principal, document, event_id, failure, observed_sha256)
                return
            except HTTPException as error:
                if error.status_code in (403, 404):
                    raise
                if (error.status_code != 503 or getattr(error, 'definite_failure', False)
                        or attempt == 1):
                    break
    logger.error('Integrity audit persistence unconfirmed; document_id=%s reviewer_id=%s event_id=%s',
                 document['id'], principal.user.id, event_id)
    raise HTTPException(503, 'Integrity audit could not be confirmed; approval denied') from None


async def list_events(gateway: SupabaseGateway, principal: Principal, limit: int, offset: int):
    params = {'select': 'id,user_id,document_id,event_type,decision,reason,created_at',
              'order': 'created_at.desc,id.desc', 'limit': str(limit), 'offset': str(offset)}
    if principal.user.role != 'admin':
        params['user_id'] = f'eq.{principal.user.id}'
    rows = await gateway.get('/rest/v1/security_events', principal.token, params)
    return [row for row in rows if principal.user.role == 'admin'
            or row.get('user_id') == str(principal.user.id)]
