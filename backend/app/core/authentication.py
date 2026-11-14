from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.supabase_client import SupabaseGateway, get_gateway
from app.schemas.responses import Me

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: Me
    token: str = field(repr=False)


async def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    gateway: Annotated[SupabaseGateway, Depends(get_gateway)],
) -> Principal:
    if credentials is None:
        raise HTTPException(401, 'Bearer access token required',
                            headers={'WWW-Authenticate': 'Bearer'})
    # Supabase Auth verifies signature and expiry server-side, including legacy HS256.
    # No locally decoded claims or user_metadata are trusted for authorization.
    user = await gateway.get('/auth/v1/user', credentials.credentials)
    try:
        user_id = str(UUID(user['id']))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, 'Invalid authenticated identity') from None
    if user.get('is_anonymous', False):
        raise HTTPException(403, 'A registered account is required')
    rows = await gateway.get('/rest/v1/profiles', credentials.credentials,
                             {'select': 'id,role,display_name', 'id': f'eq.{user_id}', 'limit': '1'})
    if (not isinstance(rows, list) or len(rows) != 1 or rows[0].get('id') != user_id
            or rows[0].get('role') not in ('student', 'admin')):
        raise HTTPException(403, 'Trusted profile required')
    return Principal(Me(id=user_id, email=user.get('email'), role=rows[0]['role'],
                        display_name=rows[0].get('display_name')), credentials.credentials)


Authenticated = Annotated[Principal, Depends(current_principal)]
