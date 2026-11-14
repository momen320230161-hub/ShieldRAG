"""Trusted server writes. This adapter never accepts a key from an HTTP client."""
import re
from uuid import UUID

import httpx
from fastapi import HTTPException, Request

from app.core.authentication import Principal
from app.core.config import Settings
from app.core.upload_limits import MAX_FILE_BYTES

BUCKET = 'shieldrag-documents'


class DocumentServiceError(HTTPException):
    def __init__(self, status_code: int, detail: str, *, definite_failure=False):
        super().__init__(status_code, detail)
        self.definite_failure = definite_failure


def object_key(user_id: UUID, document_id: UUID, extension: str) -> str:
    if extension not in ('pdf', 'txt'):
        raise ValueError('Unsupported server file extension')
    return f'ingestions/{user_id}/{document_id}.{extension}'


class DocumentStore:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    def _headers(self, principal: Principal, admin: bool = False):
        if principal.user.role not in ('student', 'admin') or (admin and principal.user.role != 'admin'):
            raise HTTPException(403, 'Admin role required' if admin else 'Access denied')
        secret = self.settings.supabase_secret_key.get_secret_value()
        if not secret.startswith('sb_secret_'):
            raise HTTPException(503, 'Document writes are not configured')
        # Modern secret keys go in apikey; never replace a user-scoped read token.
        return {'apikey': secret}

    @staticmethod
    def _check(response: httpx.Response, *, database_rpc=False):
        if response.status_code < 300:
            return
        try:
            error = response.json()
        except ValueError:
            error = {}
        code = error.get('code') if isinstance(error, dict) else None
        errors = {'PT403': (403, 'Access denied'), 'PT404': (404, 'Document not found'),
                  'PT409': (409, 'Document state or integrity conflict'),
                  'PT422': (422, 'Invalid document operation')}
        if isinstance(code, str) and code in errors:
            raise DocumentServiceError(*errors[code], definite_failure=True)
        # Authentication failures here concern the server credential, not the user.
        # A structured SQL/PostgREST error from an RPC means its transaction failed.
        # A transport/proxy/malformed response cannot establish whether it committed.
        definite = database_rpc and isinstance(code, str) and bool(
            re.fullmatch(r'(?:[0-9A-Z]{5}|PGRST[0-9]{3})', code))
        raise DocumentServiceError(503, 'Document service unavailable', definite_failure=definite)

    def ensure_available(self, principal: Principal):
        self._headers(principal)

    async def _request(self, method: str, path: str, principal: Principal, *, admin=False, **kwargs):
        headers = {**self._headers(principal, admin), **kwargs.pop('headers', {})}
        try:
            response = await self.client.request(method, self.settings.supabase_url + path,
                                                  headers=headers, **kwargs)
        except httpx.RequestError:
            raise HTTPException(503, 'Document service unavailable') from None
        self._check(response, database_rpc=path.startswith('/rest/v1/rpc/'))
        return response

    async def upload(self, principal: Principal, document_id: UUID, extension: str,
                     content_type: str, data: bytes):
        key = object_key(principal.user.id, document_id, extension)
        await self._request('POST', f'/storage/v1/object/{BUCKET}/{key}', principal,
                            content=data, headers={'Content-Type': content_type, 'x-upsert': 'false'})

    async def remove_upload(self, principal: Principal, document_id: UUID, extension: str):
        key = object_key(principal.user.id, document_id, extension)
        await self._request('DELETE', f'/storage/v1/object/{BUCKET}', principal,
                            json={'prefixes': [key]})

    async def register(self, principal: Principal, document_id: UUID, name: str,
                       extension: str, sha256: str, visibility: str):
        response = await self._request('POST', '/rest/v1/rpc/shield_register_document', principal,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id), 'p_original_name': name,
                  'p_storage_path': object_key(principal.user.id, document_id, extension),
                  'p_sha256': sha256, 'p_visibility': visibility})
        return self._row(response)

    @staticmethod
    def _row(response: httpx.Response):
        try:
            rows = response.json()
        except ValueError:
            raise HTTPException(503, 'Invalid document service response') from None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise HTTPException(503, 'Invalid document service response')
        return rows[0]

    async def upload_outcome(self, principal: Principal, document_id: UUID):
        response = await self._request('GET', '/rest/v1/documents', principal,
            params={'id': f'eq.{document_id}', 'uploaded_by': f'eq.{principal.user.id}', 'select': '*', 'limit': '1'})
        try:
            rows = response.json()
        except ValueError:
            raise HTTPException(503, 'Invalid document service response') from None
        if rows == []:
            return None
        return self._row(response)

    async def download_for_review(self, principal: Principal, document: dict) -> bytes:
        headers = self._headers(principal, admin=True)
        # Read the trusted metadata, then still enforce our canonical key format.
        key = document['storage_path']
        extension = key.rsplit('.', 1)[-1]
        if (extension not in ('pdf', 'txt') or key != object_key(
                UUID(document['uploaded_by']), UUID(document['id']), extension)):
            raise HTTPException(409, 'Document storage reference is invalid')
        try:
            async with self.client.stream('GET', self.settings.supabase_url +
                    f'/storage/v1/object/authenticated/{BUCKET}/{key}', headers=headers) as response:
                if response.status_code == 404:
                    raise HTTPException(409, 'Stored document is missing')
                if response.status_code >= 300:
                    raise HTTPException(503, 'Document service unavailable')
                result = bytearray()
                async for chunk in response.aiter_bytes(65536):
                    result.extend(chunk)
                    if len(result) > MAX_FILE_BYTES:
                        raise HTTPException(409, 'Stored document exceeds limit')
                return bytes(result)
        except httpx.RequestError:
            raise HTTPException(503, 'Document service unavailable') from None

    async def review(self, principal: Principal, document_id: UUID, decision: str,
                     sha256: str | None, reason: str | None):
        response = await self._request('POST', '/rest/v1/rpc/shield_review_document', principal, admin=True,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id),
                  'p_decision': decision, 'p_verified_sha256': sha256, 'p_reason': reason})
        return self._row(response)


def get_document_store(request: Request) -> DocumentStore:
    return request.app.state.document_store
