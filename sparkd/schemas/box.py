from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BoxBase(BaseModel):
    name: str = Field(min_length=1)
    host: str = Field(min_length=1)
    port: int = 22
    user: str = Field(min_length=1)
    ssh_key_path: str | None = None
    use_agent: bool = True
    repo_path: str = "~/spark-vllm-docker"
    tags: dict[str, str] = Field(default_factory=dict)
    # IP this box advertises on the cluster's IB/eth fabric. Used as the
    # `-n` value for cluster launches because upstream `launch-cluster.sh`
    # string-matches its own LOCAL_IP against the nodes list — hostnames
    # don't match. Auto-populated from the box's spark-vllm-docker `.env`
    # during capabilities refresh; user-editable on Box Detail.
    cluster_ip: str | None = None


class BoxCreate(BoxBase):
    pass


class BoxSpec(BoxBase):
    id: str
    created_at: datetime


class BoxCapabilities(BaseModel):
    gpu_count: int
    gpu_model: str
    vram_per_gpu_gb: int
    cuda_version: str | None = None
    ib_interface: str | None = None
    captured_at: datetime
