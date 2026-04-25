from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from sparkd.schemas.box import BoxCreate, BoxSpec
from sparkd.services.box import BoxService
from sparkd.ssh.discovery import scan_subnet

router = APIRouter(prefix="/boxes", tags=["boxes"])


def _svc(request: Request) -> BoxService:
    return request.app.state.boxes


@router.get("", response_model=list[BoxSpec])
async def list_boxes(svc: BoxService = Depends(_svc)) -> list[BoxSpec]:
    return await svc.list()


@router.post("", response_model=BoxSpec, status_code=201)
async def create_box(body: BoxCreate, svc: BoxService = Depends(_svc)) -> BoxSpec:
    return await svc.create(body)


@router.get("/{box_id}", response_model=BoxSpec)
async def get_box(box_id: str, svc: BoxService = Depends(_svc)) -> BoxSpec:
    return await svc.get(box_id)


@router.delete("/{box_id}", status_code=204)
async def delete_box(box_id: str, svc: BoxService = Depends(_svc)) -> Response:
    await svc.delete(box_id)
    return Response(status_code=204)


@router.post("/{box_id}/test")
async def test_box(box_id: str, svc: BoxService = Depends(_svc)) -> dict:
    ok = await svc.test_connection(box_id)
    return {"ok": ok}


@router.get("/{box_id}/capabilities")
async def get_caps(
    box_id: str, refresh: bool = False, svc: BoxService = Depends(_svc)
) -> dict:
    caps = await svc.capabilities(box_id, refresh=refresh)
    return caps.model_dump(mode="json")


class DiscoverRequest(BaseModel):
    cidr: str
    ssh_user: str = "ubuntu"
    ssh_port: int = 22


@router.post("/discover", status_code=202)
async def discover(body: DiscoverRequest, request: Request) -> dict:
    reg = request.app.state.jobs

    async def run() -> dict:
        probes = []
        async for p in scan_subnet(
            body.cidr, user=body.ssh_user, use_agent=True
        ):
            probes.append(p.__dict__)
        return {"probes": probes}

    job_id = await reg.submit("discover", run)
    return {"job_id": job_id}
