from __future__ import annotations

from pydantic import BaseModel, Field


class ModSpec(BaseModel):
    name: str = Field(min_length=1)
    target_models: list[str] = Field(default_factory=list)
    description: str = ""
    files: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
