from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IndexRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    external_processing_authorized: Literal[True]

    @field_validator('external_processing_authorized', mode='before')
    @classmethod
    def explicit_boolean(cls, value):
        if value is not True:
            raise ValueError('Explicit external processing authorization is required')
        return value


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1800)
    top_k: int | None = Field(None, ge=1, le=10, strict=True)

    @field_validator('question')
    @classmethod
    def bounded_utf8(cls, value: str) -> str:
        if len(value.encode('utf-8')) > 1800 or any(ord(c) < 32 and c not in '\n\t\r' for c in value):
            raise ValueError('Question exceeds the safe embedding input bound')
        return value


class IndexResult(BaseModel):
    document_id: UUID
    index_status: Literal['indexed']
    chunk_count: int
    embedding_model: str
    dimensions: Literal[768] = 768
    cached: bool = False


class Match(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page: int | None
    content: str
    similarity: float


class SearchResult(BaseModel):
    matches: list[Match]


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page: int | None
    quote: str


class AskResult(BaseModel):
    answer: str
    supported: bool
    citations: list[Citation]


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: int = Field(strict=True)
    quote: str = Field(min_length=1, max_length=500)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    supported: bool
    answer: str = Field(max_length=4000)
    evidence: list[Evidence] = Field(max_length=10)
