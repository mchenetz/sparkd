from __future__ import annotations

from pydantic import BaseModel, Field


class RecipeSpec(BaseModel):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    description: str = ""
    args: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    mods: list[str] = Field(default_factory=list)


class RecipeDiff(BaseModel):
    name: str
    added: dict[str, str]
    removed: dict[str, str]
    changed: dict[str, tuple[str, str]]
