from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from sparkd.errors import ValidationError
from sparkd.schemas.mod import ModSpec
from sparkd.schemas.upstream import UpstreamSyncRequest, UpstreamSyncResult
from sparkd.services.mod import ModService
from sparkd.services.upstream import UpstreamService

router = APIRouter(prefix="/mods", tags=["mods"])


def _svc(request: Request) -> ModService:
    return request.app.state.mods


def _upstream(request: Request) -> UpstreamService:
    return request.app.state.upstream


@router.post("/sync-upstream", response_model=UpstreamSyncResult)
async def sync_upstream(
    body: UpstreamSyncRequest,
    svc: UpstreamService = Depends(_upstream),
) -> UpstreamSyncResult:
    return await svc.sync_mods(body)


@router.get("", response_model=list[ModSpec])
def list_mods(svc: ModService = Depends(_svc)) -> list[ModSpec]:
    return svc.list()


@router.post("", response_model=ModSpec, status_code=201)
def create_mod(spec: ModSpec, svc: ModService = Depends(_svc)) -> ModSpec:
    svc.save(spec)
    return spec


@router.get("/{name}", response_model=ModSpec)
def get_mod(name: str, svc: ModService = Depends(_svc)) -> ModSpec:
    return svc.load(name)


@router.put("/{name}", response_model=ModSpec)
def put_mod(name: str, spec: ModSpec, svc: ModService = Depends(_svc)) -> ModSpec:
    if spec.name != name:
        raise ValidationError("path name and body name disagree")
    svc.save(spec)
    return spec


@router.delete("/{name}", status_code=204)
def delete_mod(name: str, svc: ModService = Depends(_svc)) -> Response:
    svc.delete(name)
    return Response(status_code=204)
