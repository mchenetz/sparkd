from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import Box
from sparkd.errors import NotFoundError, UpstreamError
from sparkd.schemas.box import BoxCapabilities, BoxCreate, BoxSpec
from sparkd.ssh.pool import SSHPool, SSHTarget


def _to_spec(row: Box) -> BoxSpec:
    return BoxSpec(
        id=row.id,
        name=row.name,
        host=row.host,
        port=row.port,
        user=row.user,
        ssh_key_path=row.ssh_key_path,
        use_agent=row.use_agent,
        repo_path=row.repo_path,
        tags=row.tags_json or {},
        created_at=row.created_at,
    )


class BoxService:
    def __init__(self, pool: SSHPool) -> None:
        self.pool = pool

    def _target_for(self, row: Box) -> SSHTarget:
        return SSHTarget(
            host=row.host,
            port=row.port,
            user=row.user,
            use_agent=row.use_agent,
            ssh_key_path=row.ssh_key_path,
        )

    async def create(self, body: BoxCreate) -> BoxSpec:
        async with session_scope() as s:
            row = Box(
                id=uuid.uuid4().hex[:12],
                name=body.name,
                host=body.host,
                port=body.port,
                user=body.user,
                ssh_key_path=body.ssh_key_path,
                use_agent=body.use_agent,
                repo_path=body.repo_path,
                tags_json=body.tags,
            )
            s.add(row)
            await s.flush()
            return _to_spec(row)

    async def list(self) -> list[BoxSpec]:
        async with session_scope() as s:
            rows = (await s.execute(select(Box))).scalars().all()
            return [_to_spec(r) for r in rows]

    async def get(self, box_id: str) -> BoxSpec:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            return _to_spec(row)

    async def delete(self, box_id: str) -> None:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            await s.delete(row)

    async def test_connection(self, box_id: str) -> bool:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
        target = self._target_for(row)
        result = await self.pool.run(target, "true")
        return result.exit_status == 0

    async def capabilities(self, box_id: str, *, refresh: bool = False) -> BoxCapabilities:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            if (
                not refresh
                and row.capabilities_json
                and row.capabilities_at
            ):
                return BoxCapabilities(**row.capabilities_json)
        target = self._target_for(row)
        gpu_q = await self.pool.run(
            target,
            "nvidia-smi --query-gpu=name,memory.total,driver_version "
            "--format=csv,noheader,nounits",
        )
        if gpu_q.exit_status != 0:
            raise UpstreamError(f"nvidia-smi failed: {gpu_q.stderr.strip()}")
        gpus = [
            tuple(p.strip() for p in line.split(","))
            for line in gpu_q.stdout.strip().splitlines()
            if line.strip()
        ]
        if not gpus:
            raise UpstreamError("nvidia-smi returned no GPUs")
        gpu_model = gpus[0][0] or "unknown"
        # nvidia-smi can report `[N/A]` for memory.total in some driver states
        # or on hosts without a real GPU. Treat any non-numeric value as 0 so
        # we still return a usable BoxCapabilities and the caller can decide.
        try:
            vram_mib = int(gpus[0][1]) if len(gpus[0]) > 1 else 0
        except (ValueError, TypeError):
            vram_mib = 0
        nvcc = await self.pool.run(target, "nvcc --version 2>/dev/null || true")
        cuda = None
        m = re.search(r"release (\S+)", nvcc.stdout)
        if m:
            cuda = m.group(1).rstrip(",")
        ib = await self.pool.run(target, "ls /sys/class/infiniband 2>/dev/null || true")
        ib_iface = ib.stdout.strip().splitlines()[0] if ib.stdout.strip() else None
        caps = BoxCapabilities(
            gpu_count=len(gpus),
            gpu_model=gpu_model,
            vram_per_gpu_gb=round(vram_mib / 1000),
            cuda_version=cuda,
            ib_interface=ib_iface,
            captured_at=datetime.now(timezone.utc),
        )
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            row.capabilities_json = caps.model_dump(mode="json")
            row.capabilities_at = caps.captured_at
        return caps
