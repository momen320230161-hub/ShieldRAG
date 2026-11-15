from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.authentication import Authenticated, Principal
from app.core.authorization import require_admin
from app.schemas.rag import AskResult, IndexRequest, IndexResult, Question, SearchResult
from app.services.indexing import index_document
from app.services.rag import ask, search

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
