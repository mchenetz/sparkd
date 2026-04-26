from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from sparkd.schemas.launch import LaunchCreate, LaunchRecord
from sparkd.services.launch import LaunchService

router = APIRouter(prefix="/launches", tags=["launches"])


def _ls(request: Request) -> LaunchService:
    return request.app.state.launches


@router.post("", response_model=LaunchRecord, status_code=201)
async def create_launch(
    body: LaunchCreate, ls: LaunchService = Depends(_ls)
) -> LaunchRecord:
    return await ls.launch(body)


@router.get("", response_model=list[LaunchRecord])
async def list_launches(
    box: str | None = None,
    active: bool = False,
    ls: LaunchService = Depends(_ls),
) -> list[LaunchRecord]:
    return await ls.list(box_id=box, active_only=active)


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
