from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from sparkd.schemas.launch import LaunchCreate, LaunchRecord
from sparkd.services.box import BoxService
from sparkd.services.launch import LaunchService
from sparkd.services.targets import resolve_target

router = APIRouter(prefix="/launches", tags=["launches"])


def _ls(request: Request) -> LaunchService:
    return request.app.state.launches


def _boxes(request: Request) -> BoxService:
    return request.app.state.boxes


@router.post("", response_model=LaunchRecord, status_code=201)
async def create_launch(
    body: LaunchCreate, ls: LaunchService = Depends(_ls)
) -> LaunchRecord:
    return await ls.launch(body)


@router.get("", response_model=list[LaunchRecord])
async def list_launches(
    target: str | None = None,
    active: bool = False,
    ls: LaunchService = Depends(_ls),
    boxes: BoxService = Depends(_boxes),
) -> list[LaunchRecord]:
    """Filter launches by target. Single-box target → query directly. Cluster
    target → union of launches across all member boxes."""
    if target and target.startswith("cluster:"):
        resolved = await resolve_target(target, boxes)
        out: list[LaunchRecord] = []
        for m in resolved.members:
            out.extend(await ls.list(box_id=m.id, active_only=active))
        return out
    return await ls.list(box_id=target, active_only=active)


@router.get("/{launch_id}", response_model=LaunchRecord)
async def get_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.get(launch_id)


@router.post("/{launch_id}/stop", response_model=LaunchRecord)
async def stop_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.stop(launch_id)


@router.post("/{launch_id}/pause", response_model=LaunchRecord)
async def pause_launch(
    launch_id: str, ls: LaunchService = Depends(_ls)
) -> LaunchRecord:
    return await ls.pause(launch_id)


@router.post("/{launch_id}/unpause", response_model=LaunchRecord)
async def unpause_launch(
    launch_id: str, ls: LaunchService = Depends(_ls)
) -> LaunchRecord:
    return await ls.unpause(launch_id)


@router.post("/{launch_id}/restart", response_model=LaunchRecord)
async def restart_launch(
    launch_id: str, ls: LaunchService = Depends(_ls)
) -> LaunchRecord:
    return await ls.restart_container(launch_id)


@router.get("/{launch_id}/inspect")
async def inspect_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> dict:
    return await ls.inspect(launch_id)


@router.get("/{launch_id}/stats")
async def launch_stats(launch_id: str, ls: LaunchService = Depends(_ls)) -> dict:
    return await ls.stats(launch_id)


@router.delete("/{launch_id}", status_code=204)
async def delete_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> Response:
    await ls.delete(launch_id)
    return Response(status_code=204)
