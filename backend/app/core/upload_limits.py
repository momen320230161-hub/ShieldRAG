from fastapi import HTTPException
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_BODY = MAX_FILE_BYTES + 64 * 1024
MAX_REVIEW_BODY = 8 * 1024
BODY_LIMIT_FLAG = 'shieldrag.upload_body_limit'


class UploadBodyLimit:
    """Bound document-write bytes before parsing, including chunked bodies."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        is_upload = scope['path'] == '/api/v1/documents'
        is_review = (scope['path'].startswith('/api/v1/documents/') and scope['path'].endswith(('/approve', '/reject', '/index'))
                     or scope['path'] in ('/api/v1/rag/search', '/api/v1/rag/ask'))
        if not is_upload and not is_review:
            return await self.app(scope, receive, send)
        limit = MAX_UPLOAD_BODY if is_upload else MAX_REVIEW_BODY
        headers = dict(scope['headers'])
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, 400)(scope, receive, send)
        if declared < 0 or declared > limit:
            return await JSONResponse({'detail': 'Request body exceeds limit'}, 413)(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > limit:
                    scope[BODY_LIMIT_FLAG] = True
                    # MultipartParser closes partial spooled files on this error.
                    # Request converts it to HTTP 400; the app maps our flag to 413.
                    if is_upload:
                        raise MultiPartException('Request body exceeds limit')
                    raise HTTPException(413, 'Request body exceeds limit')
            return message

        await self.app(scope, bounded_receive, send)
