from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class RecipeDraft(BaseModel):
    name: str
    model: str
    args: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    rationale: str = ""


class ModDraft(BaseModel):
    name: str
    target_models: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    rationale: str = ""


class AdvisorSession(BaseModel):
    id: str
    kind: Literal["recipe", "optimize", "mod"]
    target_box_id: str | None = None
    target_recipe_name: str | None = None
    hf_model_id: str | None = None
    messages: list[AdvisorMessage] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime | None = None
