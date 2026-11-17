import logging
from uuid import uuid4

import anyio
from fastapi import HTTPException

from app.security.classifier import VERSION

logger=logging.getLogger(__name__)


class SecurityStore:
    def __init__(self,documents):
        self.documents=documents

    async def record(self,principal,stage,decision,reason,document_id=None):
        event_id=uuid4()
        body={'p_actor':str(principal.user.id),'p_event_id':str(event_id),'p_stage':stage,
              'p_decision':decision,'p_reason':reason,'p_version':VERSION,
              'p_document_id':str(document_id) if document_id else None}
        with anyio.CancelScope(shield=True):
            for attempt in range(2):
                try:
                    response=await self.documents._request('POST','/rest/v1/rpc/shield_record_security_decision',
                        principal,json=body)
                    if response.json()!=str(event_id):
                        raise HTTPException(503,'Unconfirmed security audit')
                    return
                except (HTTPException,ValueError) as error:
                    if getattr(error,'definite_failure',False) or attempt==1:
                        break
        logger.error('Security audit unconfirmed; user_id=%s event_id=%s',principal.user.id,event_id)
        raise HTTPException(503,'Security audit unavailable') from None
