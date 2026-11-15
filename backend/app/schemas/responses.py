from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal['student', 'admin']


class Me(BaseModel):
    id: UUID
    email: str | None = None
    role: Role
    display_name: str | None = None


class Document(BaseModel):
    id: UUID
    original_name: str
    visibility: Literal['public', 'restricted']
    review_status: Literal['approved']
    index_status: Literal['not_indexed', 'processing', 'indexed', 'failed']
    created_at: datetime


class Documents(BaseModel):
    items: list[Document]
    limit: int
    offset: int


class DocumentMetadata(BaseModel):
    id: UUID
    uploaded_by: UUID
    original_name: str
    visibility: Literal['public', 'restricted']
    sha256: str | None
    review_status: Literal['pending', 'approved', 'rejected']
    index_status: Literal['not_indexed', 'processing', 'indexed', 'failed']
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class SecurityEvent(BaseModel):
    id: UUID
    user_id: UUID | None
    document_id: UUID | None
    event_type: str
    decision: Literal['allow', 'warn', 'review', 'deny']
    reason: str | None
    created_at: datetime


class SecurityEvents(BaseModel):
    items: list[SecurityEvent]
    limit: int
    offset: int
