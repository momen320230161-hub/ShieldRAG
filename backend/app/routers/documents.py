from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.authentication import Authenticated, Principal
from app.core.authorization import can_retrieve_document, require_admin
from app.core.upload_limits import MAX_FILE_BYTES
from app.db.document_store import DocumentStore, get_document_store
from app.db.supabase_client import SupabaseGateway, get_gateway
from app.schemas.requests import ApproveDocument, RejectDocument
from app.schemas.responses import DocumentMetadata, Documents
from app.services.documents import read_document, review_document, upload_document
from app.services.file_validation import validate_file

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


@router.post('/documents', response_model=DocumentMetadata, status_code=201, tags=['documents'],
    openapi_extra={'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
        'type': 'object', 'required': ['file'], 'additionalProperties': False,
        'properties': {'file': {'type': 'string', 'format': 'binary'},
                       'visibility': {'type': 'string', 'enum': ['public', 'restricted'], 'default': 'public'}}}}}}})
async def upload(request: Request, principal: Authenticated,
                 store: Annotated[DocumentStore, Depends(get_document_store)]):
    # Parse after authentication, and constrain parts before accepting file bytes.
    if request.headers.get('content-type', '').split(';', 1)[0].lower() != 'multipart/form-data':
        raise HTTPException(415, 'Use multipart/form-data')
    async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
        pairs = form.multi_items()
        if (set(form) - {'file', 'visibility'} or len(form.getlist('file')) != 1
                or len(form.getlist('visibility')) > 1 or len(pairs) > 2):
            raise HTTPException(422, 'Only one file and visibility are accepted')
        file = form.get('file')
        visibility = form.get('visibility', 'public')
        if not isinstance(file, UploadFile) or visibility not in ('public', 'restricted'):
            raise HTTPException(422, 'A PDF/TXT file and valid visibility are required')
        data = await file.read(MAX_FILE_BYTES + 1)
        validated = await run_in_threadpool(validate_file, file.filename or '', file.content_type or '', data)
        return await upload_document(store, principal, validated, data, visibility)


@router.get('/documents/{id}', response_model=DocumentMetadata, tags=['documents'])
async def metadata(id: UUID, principal: Authenticated,
                    gateway: Annotated[SupabaseGateway, Depends(get_gateway)]):
    return await read_document(gateway, principal, id)


@router.post('/documents/{id}/approve', response_model=DocumentMetadata, tags=['documents'])
async def approve(id: UUID, body: ApproveDocument,
                  principal: Annotated[Principal, Depends(require_admin)],
                  gateway: Annotated[SupabaseGateway, Depends(get_gateway)],
                  store: Annotated[DocumentStore, Depends(get_document_store)]):
    return await review_document(gateway, store, principal, id, 'approved')


@router.post('/documents/{id}/reject', response_model=DocumentMetadata, tags=['documents'])
async def reject(id: UUID, body: RejectDocument,
                 principal: Annotated[Principal, Depends(require_admin)],
                 gateway: Annotated[SupabaseGateway, Depends(get_gateway)],
                 store: Annotated[DocumentStore, Depends(get_document_store)]):
    return await review_document(gateway, store, principal, id, 'rejected', body.reason)
