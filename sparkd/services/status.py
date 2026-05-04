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


# ---------- fleet-level snapshot (cluster-aware) ----------


@dataclass
class FleetMember:
    """One node within a cluster (or standalone box) — light projection
    suitable for the Status fleet view. Heavy details (per-container
    table) live on the per-box snapshot drilldown."""

    box_id: str
    box_name: str
    role: str               # "head" | "worker" | "standalone"
    connectivity: str       # "online" | "offline" | "unknown"
    container_id: str | None = None   # the active launch's container, if any
    container_image: str | None = None


@dataclass
class FleetLaunch:
    """The shape of a launch as the fleet view needs it. Mirrors the
    reconciler-driven DB state — no re-probing here."""

    id: str
    recipe_name: str
    state: str              # 'starting' | 'healthy' | 'paused' | 'failed' |
                            # 'stopped' | 'interrupted'
    box_id: str             # the head box (matches the launch DB row)
    cluster_name: str | None
    container_id: str | None  # head's container, recorded by reconciler
    started_at: datetime
    exit_info: dict | None


@dataclass
class FleetCluster:
    name: str
    members: list[FleetMember]
    active_launch: FleetLaunch | None  # one active launch shown per cluster


@dataclass
class FleetStandalone:
    member: FleetMember
    active_launch: FleetLaunch | None


@dataclass
class FleetSnapshot:
    """One-shot view of the whole fleet — clusters first, standalones
    second, drift last. Built by reading the launch DB (the reconciler
    keeps it current) plus a single docker ps per box. No /health
    re-probe — that's the reconciler's job and its results are already
    on Launch.state."""

    clusters: list[FleetCluster] = field(default_factory=list)
    standalones: list[FleetStandalone] = field(default_factory=list)
    # External containers we found on a box that aren't claimed by any
    # active launch — could be hand-started vLLM, a forgotten image,
    # or upstream's worker-side container that we couldn't trace back
    # to its head's launch.
    drift_external_containers: list[dict] = field(default_factory=list)
    # Launches in the DB whose container can't be located anywhere on
    # any member.
    drift_orphan_launches: list[str] = field(default_factory=list)
    captured_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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


    # ---------- fleet snapshot ----------

    async def _docker_ps_safe(
        self, box_id: str
    ) -> tuple[str, list[DockerContainer]]:
        """`_docker_ps` but tolerant of an offline box. Returns
        (connectivity, containers); connectivity is 'online' on success,
        'offline' on any SSH/docker failure."""
        try:
            return "online", await self._docker_ps(box_id)
        except Exception:  # noqa: BLE001
            return "offline", []

    async def fleet_snapshot(self) -> FleetSnapshot:
        """Build a cluster-aware view of the whole fleet in one shot.

        Reads:
          - all boxes (BoxService.list)
          - their cluster groupings (BoxService.list_clusters)
          - active launches (state in {starting, healthy, paused})
            from the DB — this is the reconciler-maintained source of
            truth, no /health re-probe here
          - one `docker ps` per online box

        Composes:
          - per cluster: members[], at-most-one active launch
          - per standalone: single member, optional active launch
          - drift: external containers (no matching launch), orphan
            launches (DB row exists but no container anywhere)
        """
        # 1. Gather boxes + cluster groupings.
        all_boxes = await self.boxes.list()
        boxes_by_id = {b.id: b for b in all_boxes}
        groups = await self.boxes.list_clusters()
        # box_id → cluster_name (or None).
        cluster_of: dict[str, str | None] = {b.id: None for b in all_boxes}
        for cname, members in groups.items():
            for b in members:
                cluster_of[b.id] = cname

        # 2. Active launches from the DB.
        async with session_scope() as s:
            launch_rows = (
                await s.execute(
                    select(Launch).where(
                        Launch.state.in_(["starting", "healthy", "paused"])
                    )
                )
            ).scalars().all()
            launches_by_id = {
                row.id: FleetLaunch(
                    id=row.id,
                    recipe_name=row.recipe_name,
                    state=row.state,
                    box_id=row.box_id,
                    cluster_name=row.cluster_name,
                    container_id=row.container_id,
                    started_at=row.started_at,
                    exit_info=row.exit_info_json,
                )
                for row in launch_rows
            }
        # head_box_id → launch (one active per box; if multiple, pick
        # the most recent — UI shows just one anyway).
        active_by_head: dict[str, FleetLaunch] = {}
        for lid, l in sorted(
            launches_by_id.items(), key=lambda kv: kv[1].started_at
        ):
            active_by_head[l.box_id] = l
        # cluster_name → launch (a cluster's launch is on its head box).
        active_by_cluster: dict[str, FleetLaunch] = {}
        for l in active_by_head.values():
            if l.cluster_name:
                active_by_cluster[l.cluster_name] = l

        # 3. docker ps per box, in parallel.
        import asyncio

        ps_results = await asyncio.gather(
            *(self._docker_ps_safe(b.id) for b in all_boxes),
            return_exceptions=False,
        )
        ps_by_box: dict[str, tuple[str, list[DockerContainer]]] = {
            b.id: ps_results[i] for i, b in enumerate(all_boxes)
        }

        # 4. Compose member projections.
        def member_for(
            box_id: str, role: str, claimed_cid: str | None
        ) -> FleetMember:
            box = boxes_by_id[box_id]
            connectivity, containers = ps_by_box[box_id]
            cid = claimed_cid
            image: str | None = None
            if cid:
                # Verify the launch's claimed container is actually on
                # this box — if not, leave cid None (drift fires below).
                match = next(
                    (c for c in containers if c.id.startswith(cid[:12])),
                    None,
                )
                if match is None:
                    cid = None
                else:
                    image = match.image
            return FleetMember(
                box_id=box_id,
                box_name=box.name,
                role=role,
                connectivity=connectivity,
                container_id=cid,
                container_image=image,
            )

        # 5. Build clusters list.
        snap = FleetSnapshot()
        for cname, members in sorted(groups.items()):
            head_box = members[0]
            cluster_launch = active_by_cluster.get(cname)
            head_cid = (
                cluster_launch.container_id
                if cluster_launch
                and cluster_launch.box_id == head_box.id
                else None
            )
            fleet_members: list[FleetMember] = []
            for i, b in enumerate(members):
                role = "head" if i == 0 else "worker"
                # The DB only tracks the head's container_id. For workers,
                # we still surface their /docker ps row so the UI can
                # show "this worker is part of the cluster's launch" but
                # we can't pin it to a specific launch's container_id.
                claimed = (
                    head_cid if role == "head" and cluster_launch else None
                )
                fleet_members.append(member_for(b.id, role, claimed))
            snap.clusters.append(
                FleetCluster(
                    name=cname,
                    members=fleet_members,
                    active_launch=cluster_launch,
                )
            )

        # 6. Standalones: every box not in a cluster.
        for b in sorted(all_boxes, key=lambda x: x.name):
            if cluster_of[b.id] is not None:
                continue
            launch = active_by_head.get(b.id)
            claimed = launch.container_id if launch else None
            snap.standalones.append(
                FleetStandalone(
                    member=member_for(b.id, "standalone", claimed),
                    active_launch=launch,
                )
            )

        # 7. Drift detection.
        # 7a. External containers: any container on any box with image
        #     'vllm-node' (or whose label sparkd.launch is set) that
        #     isn't claimed by an active launch on its box (single-box)
        #     or its cluster's head (cluster member).
        claimed_cids: set[tuple[str, str]] = set()
        for c in snap.clusters:
            for m in c.members:
                if m.container_id:
                    claimed_cids.add((m.box_id, m.container_id[:12]))
        for s in snap.standalones:
            if s.member.container_id:
                claimed_cids.add(
                    (s.member.box_id, s.member.container_id[:12])
                )
        for box in all_boxes:
            connectivity, containers = ps_by_box[box.id]
            if connectivity != "online":
                continue
            box_cluster = cluster_of[box.id]
            for c in containers:
                short = c.id[:12]
                if (box.id, short) in claimed_cids:
                    continue
                # On a cluster worker: accept the worker's container as
                # part of the cluster's active launch even though we
                # don't track its id explicitly.
                if box_cluster and box_cluster in active_by_cluster:
                    # Heuristic: if it's the vllm-node image and the
                    # cluster has an active launch, presume it's the
                    # worker side of that launch.
                    if c.image and "vllm-node" in c.image:
                        continue
                # Genuine external container.
                snap.drift_external_containers.append(
                    {
                        "box_id": box.id,
                        "box_name": box.name,
                        "container_id": short,
                        "image": c.image,
                        "state": c.state,
                    }
                )

        # 7b. Orphan launches: an active launch DB row whose head box
        #     reports no matching container.
        for l in launches_by_id.values():
            head_member = next(
                (
                    m
                    for cluster in snap.clusters
                    for m in cluster.members
                    if m.box_id == l.box_id
                ),
                None,
            )
            standalone_member = next(
                (
                    s.member
                    for s in snap.standalones
                    if s.member.box_id == l.box_id
                ),
                None,
            )
            member = head_member or standalone_member
            if member and member.container_id:
                continue
            # Container missing on the head — orphan.
            snap.drift_orphan_launches.append(l.id)

        return snap
