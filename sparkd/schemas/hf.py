from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HFModelInfo(BaseModel):
    id: str
    architecture: str = ""
    parameters_b: float = 0.0
    context_length: int = 0
    supported_dtypes: list[str] = Field(default_factory=list)
    license: str = ""
    pipeline_tag: str = ""
    fetched_at: datetime | None = None
