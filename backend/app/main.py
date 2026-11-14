from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.upload_limits import BODY_LIMIT_FLAG, UploadBodyLimit
from app.db.supabase_client import SupabaseGateway
from app.db.document_store import DocumentStore
from app.routers import auth, documents, security


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or get_settings()
        async with httpx.AsyncClient(timeout=10, transport=transport, trust_env=False,
                                     follow_redirects=False) as client:
            app.state.gateway = SupabaseGateway(client, config)
            app.state.document_store = DocumentStore(client, config)
            yield

    app = FastAPI(title='ShieldRAG Backend', version='0.1.0', lifespan=lifespan)
    app.add_middleware(UploadBodyLimit)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        if request.scope.get(BODY_LIMIT_FLAG):
            return JSONResponse({'detail': 'Request body exceeds limit'}, status_code=413)
        return await http_exception_handler(request, error)

    @app.get('/health', tags=['operations'])
    def health():
        # Liveness only. Integration probes separately check Auth and PostgREST.
        return {'status': 'ok'}

    for router in (auth.router, documents.router, security.router):
        app.include_router(router, prefix='/api/v1')
    return app


app = create_app()
