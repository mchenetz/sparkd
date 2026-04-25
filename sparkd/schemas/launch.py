from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LaunchState(str, Enum):
    starting = "starting"
    healthy = "healthy"
    failed = "failed"
    stopped = "stopped"
    interrupted = "interrupted"


class LaunchCreate(BaseModel):
    recipe: str = Field(min_length=1)
    box_id: str = Field(min_length=1)
    mods: list[str] = Field(default_factory=list)
    overrides: dict[str, str] = Field(default_factory=dict)


class LaunchRecord(BaseModel):
    id: str
    box_id: str
    recipe_name: str
    state: LaunchState
    container_id: str | None
    command: str
    started_at: datetime
    stopped_at: datetime | None
    exit_info: dict[str, Any] | None
