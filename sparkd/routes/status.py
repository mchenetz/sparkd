from __future__ import annotations

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
