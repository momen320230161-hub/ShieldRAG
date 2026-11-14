from app.core.authentication import Principal
from app.db.supabase_client import SupabaseGateway


async def list_events(gateway: SupabaseGateway, principal: Principal, limit: int, offset: int):
    params = {'select': 'id,user_id,document_id,event_type,decision,reason,created_at',
              'order': 'created_at.desc,id.desc', 'limit': str(limit), 'offset': str(offset)}
    if principal.user.role != 'admin':
        params['user_id'] = f'eq.{principal.user.id}'
    rows = await gateway.get('/rest/v1/security_events', principal.token, params)
    return [row for row in rows if principal.user.role == 'admin'
            or row.get('user_id') == str(principal.user.id)]
