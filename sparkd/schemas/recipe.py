from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def _to_str_dict(v: Any) -> Any:
    """Coerce None → {} and any scalar values to strings.

    Upstream recipe YAMLs sometimes leave `env:` empty (parsed as None) or use
    int/bool values for env vars (e.g. `VLLM_MARLIN_USE_ATOMIC_ADD: 1`).
    These are harmless — env vars are strings at the OS level — so we accept
    them and stringify on the way in. The on-disk YAML is preserved verbatim
    by LibraryService.save_recipe_raw; this normalization only affects the
    parsed view.
    """
    if v is None:
        return {}
    if isinstance(v, dict):
        return {str(k): "" if val is None else str(val) for k, val in v.items()}
    return v


def _to_list(v: Any) -> Any:
    if v is None:
        return []
    return v


def _to_str(v: Any) -> Any:
    if v is None:
        return ""
    return v


class RecipeSpec(BaseModel):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    description: str = ""
    args: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    mods: list[str] = Field(default_factory=list)

    @field_validator("args", "env", mode="before")
    @classmethod
    def _coerce_string_dict(cls, v: Any) -> Any:
        return _to_str_dict(v)

    @field_validator("mods", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> Any:
        return _to_list(v)

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> Any:
        return _to_str(v)


class RecipeDiff(BaseModel):
    name: str
    added: dict[str, str]
    removed: dict[str, str]
    changed: dict[str, tuple[str, str]]
