from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from app.core.authentication import Authenticated, Principal
from app.core.authorization import require_admin
from app.schemas.rag import AskResult, IndexRequest, IndexResult, Question, SearchResult
from app.services.indexing import index_document
from app.services.rag import ask, search
from app.schemas.security import SecureResult
from app.services.secure_rag import secure_ask

router = APIRouter(tags=['rag'])


@router.post('/documents/{id}/index', response_model=IndexResult)
async def index(id: UUID, body: IndexRequest, request: Request,
                principal: Annotated[Principal, Depends(require_admin)]):
    state = request.app.state
    return await index_document(state.gateway, state.document_store, state.rag_store,
                                state.gemini, principal, id, state.settings)


@router.post('/rag/search', response_model=SearchResult)
async def retrieve(body: Question, request: Request, principal: Authenticated):
    state = request.app.state
    return {'matches': await search(state.gateway, state.gemini, principal, body, state.settings)}


@router.post('/rag/ask', response_model=AskResult)
async def answer(body: Question, request: Request, principal: Authenticated):
    state = request.app.state
    return await ask(state.gateway, state.gemini, principal, body, state.settings)


@router.post('/rag/secure-ask',response_model=SecureResult,responses={503:{'model':SecureResult}})
async def secure_answer(body:Question,request:Request,principal:Authenticated):
    state=request.app.state
    result=await secure_ask(state.gateway,state.gemini,state.security_agent,state.security_store,
                          principal,body,state.settings)
    if result.status=='unavailable':
        return JSONResponse(result.model_dump(mode='json'),status_code=503)
    return result
