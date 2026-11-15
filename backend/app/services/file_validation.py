import io
import logging
import re
from dataclasses import dataclass

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.generic import ArrayObject, StreamObject

from app.core.upload_limits import MAX_FILE_BYTES

# Parser warnings may contain source bytes. Keep them out of application logs.
logging.getLogger('pypdf').addHandler(logging.NullHandler())
logging.getLogger('pypdf').propagate = False


@dataclass(frozen=True)
class ValidatedFile:
    original_name: str
    extension: str
    content_type: str


def validate_file(filename: str, content_type: str, data: bytes) -> ValidatedFile:
    # The name is metadata only; no client-controlled string becomes a Storage key.
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._ -]{0,194}\.(pdf|txt)', filename, re.I)
            or '..' in filename or filename.split('.')[0].upper() in {
                'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)],
                *[f'LPT{i}' for i in range(1, 10)]}):
        raise HTTPException(422, 'Unsafe or unsupported filename')
    if not data:
        raise HTTPException(422, 'Empty documents are not accepted')
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, 'File exceeds 10 MiB')
    extension = filename.rsplit('.', 1)[1].lower()
    expected_mime = 'application/pdf' if extension == 'pdf' else 'text/plain'
    if content_type.lower().split(';', 1)[0].strip() != expected_mime:
        raise HTTPException(415, 'File type and MIME type must match')
    if extension == 'txt':
        try:
            text = data.decode('utf-8-sig', errors='strict')
        except UnicodeDecodeError:
            raise HTTPException(422, 'TXT documents must be valid UTF-8') from None
        if (not text.strip() or any(ord(c) < 32 and c not in '\t\r\n' for c in text)
                or data.lstrip().startswith((b'%PDF-', b'PK\x03\x04', b'MZ'))):
            raise HTTPException(422, 'Invalid text document content')
    else:
        if not re.match(rb'%PDF-(1\.[0-7]|2\.0)[\r\n]', data) or not re.search(rb'%%EOF\s*$', data):
            raise HTTPException(422, 'Malformed PDF document')
        try:
            with PdfReader(io.BytesIO(data), strict=True, xref_stream_maximum_entries=100000) as reader:
                if reader.is_encrypted or reader.root_object.get('/Type') != '/Catalog':
                    raise ValueError('Unsupported PDF structure')
                # Resolve page objects without extracting/decompressing page content.
                # No text extraction, chunking, embedding or indexing occurs here.
                pages = reader.pages
                if not 1 <= len(pages) <= 1000:
                    raise ValueError('Unsupported page count')
                for page in pages:
                    if page.get('/Type') != '/Page' or len(page.mediabox) != 4:
                        raise ValueError('Invalid page structure')
                    contents = page.get('/Contents')
                    if contents is not None:
                        contents = contents.get_object()
                        streams = contents if isinstance(contents, ArrayObject) else [contents]
                        if any(not isinstance(stream.get_object(), StreamObject) for stream in streams):
                            raise ValueError('Invalid page content stream reference')
        except Exception:
            # Parser diagnostics can include content. Do not expose their text.
            raise HTTPException(422, 'Malformed, encrypted, or unsupported PDF document') from None
    return ValidatedFile(filename, extension, expected_mime)
