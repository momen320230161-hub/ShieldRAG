from typing import Literal

from pydantic import BaseModel

from app.schemas.rag import Citation


class SecuritySummary(BaseModel):
    threat_detected: bool
    risk_level: Literal['low','medium','high','unknown']
    threat_category: str
    reason_code: str


class SecureResult(BaseModel):
    decision: Literal['allow','block','review']
    status: Literal['answered','blocked','insufficient_evidence','unavailable']
    answer: str | None=None
    supported: bool=False
    citations: list[Citation]=[]
    security: SecuritySummary
