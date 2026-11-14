from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.authentication import Authenticated
from app.core.authorization import can_retrieve_document
from app.db.supabase_client import SupabaseGateway, get_gateway
from app.schemas.responses import Documents

router = APIRouter()


@router.get('/documents', response_model=Documents, tags=['documents'])
async def documents(
    principal: Authenticated,
    gateway: Annotated[SupabaseGateway, Depends(get_gateway)],
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    params = {'select': 'id,original_name,visibility,review_status,index_status,created_at',
              'review_status': 'eq.approved', 'order': 'created_at.desc,id.desc',
              'limit': str(limit), 'offset': str(offset)}
    if principal.user.role == 'student':
        params['visibility'] = 'eq.public'
    rows = await gateway.get('/rest/v1/documents', principal.token, params)
    return {'items': [row for row in rows if can_retrieve_document(principal.user.role, row)],
            'limit': limit, 'offset': offset}
