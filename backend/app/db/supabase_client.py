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
        if response.status_code in (401, 403) and path == '/auth/v1/user':
            raise HTTPException(401, 'Invalid or expired access token',
                                headers={'WWW-Authenticate': 'Bearer'})
        if response.status_code >= 300:
            # Never return upstream error bodies, request headers, or credentials.
            raise HTTPException(503, 'Supabase request failed')
        try:
            return response.json()
        except ValueError:
            raise HTTPException(503, 'Invalid Supabase response') from None


def get_gateway(request: Request) -> SupabaseGateway:
    return request.app.state.gateway
