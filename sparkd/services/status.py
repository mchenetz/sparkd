from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import Box, Launch
from sparkd.errors import NotFoundError
from sparkd.services.box import BoxService
from sparkd.ssh.pool import SSHPool


@dataclass
class DockerContainer:
    id: str
    image: str
    labels: dict[str, str]
    state: str


@dataclass
class RunningModel:
    container_id: str
    launch_id: str | None
    recipe_name: str | None
    vllm_model_id: str | None
    healthy: bool
    source: str  # "dashboard" | "external"


@dataclass
class BoxStatusSnapshot:
    box_id: str
    connectivity: str  # "online" | "offline" | "degraded"
    running_models: list[RunningModel] = field(default_factory=list)
    drift_missing_container: list[str] = field(default_factory=list)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def reconcile(
    *,
    containers: list[DockerContainer],
    launches: dict[str, str],
    vllm_models: list[str],
    vllm_healthy: bool,
    box_id: str = "",
) -> BoxStatusSnapshot:
    snap = BoxStatusSnapshot(box_id=box_id, connectivity="online")
    seen_launch_ids: set[str] = set()
    for c in containers:
        launch_id = c.labels.get("sparkd.launch")
        recipe_name = launches.get(launch_id) if launch_id else None
        source = "dashboard" if launch_id and launch_id in launches else "external"
        if launch_id and launch_id in launches:
            seen_launch_ids.add(launch_id)
        model_id = vllm_models[0] if vllm_models else None
        snap.running_models.append(
            RunningModel(
                container_id=c.id,
                launch_id=launch_id,
                recipe_name=recipe_name,
                vllm_model_id=model_id,
                healthy=vllm_healthy and model_id is not None,
                source=source,
            )
        )
    for lid in launches:
        if lid not in seen_launch_ids:
            snap.drift_missing_container.append(lid)
    return snap


class StatusService:
    def __init__(self, boxes: BoxService, pool: SSHPool) -> None:
        self.boxes = boxes
        self.pool = pool

    async def _docker_ps(self, box_id: str) -> list[DockerContainer]:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            target = self.boxes._target_for(row)
        result = await self.pool.run(target, "docker ps --format '{{json .}}'")
        out: list[DockerContainer] = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            labels: dict[str, str] = {}
            if d.get("Labels"):
                for kv in d["Labels"].split(","):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        labels[k.strip()] = v.strip()
            out.append(
                DockerContainer(
                    id=d.get("ID", "")[:12],
                    image=d.get("Image", ""),
                    labels=labels,
                    state=d.get("State", ""),
                )
            )
        return out

    async def _vllm_probe(self, box_host: str, port: int = 8000) -> tuple[list[str], bool]:
        async with httpx.AsyncClient(timeout=1.0) as client:
            try:
                models_r = await client.get(f"http://{box_host}:{port}/v1/models")
                health_r = await client.get(f"http://{box_host}:{port}/health")
                models = [m["id"] for m in models_r.json().get("data", [])]
                return models, health_r.status_code == 200
            except (httpx.HTTPError, ValueError, KeyError):
                return [], False

    async def snapshot(self, box_id: str) -> BoxStatusSnapshot:
        async with session_scope() as s:
            box_row = await s.get(Box, box_id)
            if box_row is None:
                raise NotFoundError("box", box_id)
            host = box_row.host
            launch_rows = (
                await s.execute(
                    select(Launch).where(
                        Launch.box_id == box_id,
                        Launch.state.in_(["starting", "healthy"]),
                    )
                )
            ).scalars().all()
            launches = {l.id: l.recipe_name for l in launch_rows}
        try:
            containers = await self._docker_ps(box_id)
            connectivity = "online"
        except Exception:
            return BoxStatusSnapshot(box_id=box_id, connectivity="offline")
        models, healthy = await self._vllm_probe(host)
        snap = reconcile(
            containers=containers,
            launches=launches,
            vllm_models=models,
            vllm_healthy=healthy,
            box_id=box_id,
        )
        snap.connectivity = connectivity
        return snap
