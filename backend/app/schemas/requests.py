from pydantic import BaseModel, ConfigDict, Field


class ApproveDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RejectDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)
