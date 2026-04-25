from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobState(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    interrupted = "interrupted"


class Job(BaseModel):
    id: str
    kind: str
    state: JobState
    progress: float = 0.0
    message: str = ""
    result: dict | None = None
    started_at: datetime
    finished_at: datetime | None = None
