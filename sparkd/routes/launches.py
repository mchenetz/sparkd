from __future__ import annotations

from fastapi import APIRouter, Depends, Request

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
    box: str | None = None, ls: LaunchService = Depends(_ls)
) -> list[LaunchRecord]:
    return await ls.list(box_id=box)


@router.get("/{launch_id}", response_model=LaunchRecord)
async def get_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.get(launch_id)


@router.post("/{launch_id}/stop", response_model=LaunchRecord)
async def stop_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.stop(launch_id)
