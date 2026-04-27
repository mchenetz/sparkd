from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LaunchState(str, Enum):
    starting = "starting"
    healthy = "healthy"
    paused = "paused"
    failed = "failed"
    stopped = "stopped"
    interrupted = "interrupted"


ACTIVE_STATES = frozenset({"starting", "healthy", "paused"})


class LaunchCreate(BaseModel):
    recipe: str = Field(min_length=1)
    target: str = Field(min_length=1)  # box id, or "cluster:<name>"
    mods: list[str] = Field(default_factory=list)
    overrides: dict[str, str] = Field(default_factory=dict)


class LaunchRecord(BaseModel):
    id: str
    box_id: str  # head box for cluster launches; SSH-anchored
    cluster_name: str | None = None  # populated for cluster targets
    recipe_name: str
    state: LaunchState
    container_id: str | None
    command: str
    log_path: str | None = None
    started_at: datetime
    stopped_at: datetime | None
    exit_info: dict[str, Any] | None
