from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.db.supabase_client import SupabaseGateway
from app.routers import auth, documents, security


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or get_settings()
        async with httpx.AsyncClient(timeout=10, transport=transport, trust_env=False,
                                     follow_redirects=False) as client:
            app.state.gateway = SupabaseGateway(client, config)
            yield

    app = FastAPI(title='ShieldRAG Backend', version='0.1.0', lifespan=lifespan)

    @app.get('/health', tags=['operations'])
    def health():
        # Liveness only. Integration probes separately check Auth and PostgREST.
        return {'status': 'ok'}

    for router in (auth.router, documents.router, security.router):
        app.include_router(router, prefix='/api/v1')
    return app


app = create_app()
