from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request

from sparkd.services.status import StatusService

router = APIRouter(tags=["status"])


def _svc(request: Request) -> StatusService:
    return request.app.state.status


@router.get("/boxes/{box_id}/status")
async def get_status(box_id: str, svc: StatusService = Depends(_svc)) -> dict:
    snap = await svc.snapshot(box_id)
    return {
        "box_id": snap.box_id,
        "connectivity": snap.connectivity,
        "running_models": [m.__dict__ for m in snap.running_models],
        "drift_missing_container": snap.drift_missing_container,
        "captured_at": snap.captured_at.isoformat(),
    }


@router.get("/status/fleet")
async def get_fleet_status(svc: StatusService = Depends(_svc)) -> dict:
    """Cluster-aware view of the whole fleet — clusters first,
    standalones second, drift last. The Status page renders this in
    one shot so the user sees what's running across every member at a
    glance, without picking-each-box-to-piece-it-together."""
    snap = await svc.fleet_snapshot()
    return {
        "clusters": [
            {
                "name": c.name,
                "members": [asdict(m) for m in c.members],
                "active_launch": _launch_dict(c.active_launch),
            }
            for c in snap.clusters
        ],
        "standalones": [
            {
                "member": asdict(s.member),
                "active_launch": _launch_dict(s.active_launch),
            }
            for s in snap.standalones
        ],
        "drift_external_containers": snap.drift_external_containers,
        "drift_orphan_launches": snap.drift_orphan_launches,
        "captured_at": snap.captured_at.isoformat(),
    }


def _launch_dict(launch) -> dict | None:
    if launch is None:
        return None
    d = asdict(launch)
    d["started_at"] = launch.started_at.isoformat()
    return d
