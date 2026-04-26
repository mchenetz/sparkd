from __future__ import annotations

from pydantic import BaseModel, Field


class UpstreamSyncRequest(BaseModel):
    repo: str = "eugr/spark-vllm-docker"
    branch: str = "main"
    force: bool = False


class UpstreamSyncError(BaseModel):
    name: str
    message: str


class UpstreamSyncResult(BaseModel):
    repo: str
    branch: str
    imported: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    errors: list[UpstreamSyncError] = Field(default_factory=list)
