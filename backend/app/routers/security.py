from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.authentication import Authenticated
from app.db.supabase_client import SupabaseGateway, get_gateway
from app.schemas.responses import SecurityEvents
from app.services.audit import list_events

router = APIRouter()


@router.get('/security/events', response_model=SecurityEvents, tags=['security'])
async def events(principal: Authenticated,
                 gateway: Annotated[SupabaseGateway, Depends(get_gateway)],
                 limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return {'items': await list_events(gateway, principal, limit, offset),
            'limit': limit, 'offset': offset}
