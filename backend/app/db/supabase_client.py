import httpx
from fastapi import HTTPException, Request

from app.core.config import Settings


class SupabaseGateway:
    """Stateless REST adapter: never store a user's token on the shared client."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def get(self, path: str, token: str, params: dict | None = None):
        try:
            response = await self.client.get(
                self.settings.supabase_url + path,
                headers={
                    'apikey': self.settings.supabase_publishable_key.get_secret_value(),
                    'Authorization': f'Bearer {token}',
                },
                params=params,
            )
        except httpx.RequestError:
            raise HTTPException(503, 'Supabase unavailable') from None
        auth_failure = False
        if path == '/auth/v1/user' and response.status_code in (401, 403):
            try:
                error = response.json()
            except ValueError:
                error = {}
            # Auth sometimes returns 403 for invalid JWTs. Read only documented
            # codes; never echo error messages, descriptions, or upstream bodies.
            if isinstance(error, dict):
                auth_failure = error.get('error_code', error.get('code')) in (
                    'bad_jwt', 'session_expired', 'session_not_found', 'user_not_found')
        if response.status_code == 401 or auth_failure:
            raise HTTPException(401, 'Invalid or expired access token',
                                headers={'WWW-Authenticate': 'Bearer'})
        if response.status_code == 403:
            raise HTTPException(403, 'Access denied')
        if response.status_code >= 300:
            # Never return upstream error bodies, request headers, or credentials.
            raise HTTPException(503, 'Supabase request failed')
        try:
            payload = response.json()
        except ValueError:
            raise HTTPException(503, 'Invalid Supabase response') from None
        expected_type = dict if path == '/auth/v1/user' else list
        if not isinstance(payload, expected_type):
            raise HTTPException(503, 'Invalid Supabase response')
        if isinstance(payload, list) and any(not isinstance(row, dict) for row in payload):
            raise HTTPException(503, 'Invalid Supabase response')
        return payload


def get_gateway(request: Request) -> SupabaseGateway:
    return request.app.state.gateway
