from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from sparkd.errors import ValidationError
from sparkd.schemas.recipe import RecipeSpec
from sparkd.schemas.upstream import UpstreamSyncRequest, UpstreamSyncResult
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.services.upstream import UpstreamService
from sparkd.services.versions import RecipeVersionService


class RecipeRawBody(BaseModel):
    yaml: str


class RecipeRawResponse(BaseModel):
    yaml: str
    name: str


class RevertBody(BaseModel):
    note: str | None = None


router = APIRouter(prefix="/recipes", tags=["recipes"])


def _lib(request: Request) -> LibraryService:
    return request.app.state.library


def _rs(request: Request) -> RecipeService:
    return request.app.state.recipes


def _upstream(request: Request) -> UpstreamService:
    return request.app.state.upstream


def _versions(request: Request) -> RecipeVersionService:
    return request.app.state.recipe_versions


async def _record_current(
    name: str,
    lib: LibraryService,
    versions: RecipeVersionService,
    *,
    source: str,
    note: str | None = None,
) -> None:
    try:
        text = lib.load_recipe_text(name)
    except Exception:  # noqa: BLE001
        return
    await versions.record(name, text, source=source, note=note)


@router.post("/sync-upstream", response_model=UpstreamSyncResult)
async def sync_upstream(
    body: UpstreamSyncRequest,
    svc: UpstreamService = Depends(_upstream),
) -> UpstreamSyncResult:
    return await svc.sync(body)


@router.get("", response_model=list[RecipeSpec])
def list_recipes(box: str | None = None, lib: LibraryService = Depends(_lib)) -> list[RecipeSpec]:
    return lib.list_recipes(box_id=box)


@router.post("", response_model=RecipeSpec, status_code=201)
async def create_recipe(
    spec: RecipeSpec,
    lib: LibraryService = Depends(_lib),
    versions: RecipeVersionService = Depends(_versions),
) -> RecipeSpec:
    lib.save_recipe(spec)
    await _record_current(spec.name, lib, versions, source="manual", note="created")
    return spec


@router.get("/{name}", response_model=RecipeSpec)
def get_recipe(
    name: str, box: str | None = None, lib: LibraryService = Depends(_lib)
) -> RecipeSpec:
    return lib.load_recipe(name, box_id=box)


@router.put("/{name}", response_model=RecipeSpec)
async def put_recipe(
    name: str,
    spec: RecipeSpec,
    lib: LibraryService = Depends(_lib),
    versions: RecipeVersionService = Depends(_versions),
) -> RecipeSpec:
    if spec.name != name:
        raise ValidationError("path name and body name disagree")
    lib.update_recipe(spec)
    await _record_current(name, lib, versions, source="manual", note="edited via form")
    return spec


@router.get("/{name}/raw", response_model=RecipeRawResponse)
def get_recipe_raw(
    name: str,
    box: str | None = None,
    lib: LibraryService = Depends(_lib),
) -> RecipeRawResponse:
    text = lib.load_recipe_text(name, box_id=box)
    return RecipeRawResponse(name=name, yaml=text)


@router.put("/{name}/raw", response_model=RecipeSpec)
async def put_recipe_raw(
    name: str,
    body: RecipeRawBody,
    lib: LibraryService = Depends(_lib),
    versions: RecipeVersionService = Depends(_versions),
) -> RecipeSpec:
    spec = lib.save_recipe_raw(name, body.yaml)
    await versions.record(name, body.yaml, source="raw", note="edited yaml")
    return spec


@router.delete("/{name}", status_code=204)
async def delete_recipe(
    name: str,
    lib: LibraryService = Depends(_lib),
    versions: RecipeVersionService = Depends(_versions),
) -> Response:
    lib.delete_recipe(name)
    await versions.delete_for(name)
    return Response(status_code=204)


@router.post("/{name}/validate")
async def validate_recipe(
    name: str,
    box: str,
    lib: LibraryService = Depends(_lib),
    rs: RecipeService = Depends(_rs),
) -> dict:
    spec = lib.load_recipe(name, box_id=box)
    issues = await rs.validate(spec, box)
    return {"ok": not issues, "issues": issues}


@router.post("/{name}/sync")
async def sync_recipe(
    name: str, box: str, rs: RecipeService = Depends(_rs)
) -> dict:
    await rs.sync(name, box)
    return {"ok": True}


# ----- versioning -----


@router.get("/{name}/versions")
async def list_versions(
    name: str, versions: RecipeVersionService = Depends(_versions)
) -> dict:
    rows = await versions.list(name)
    return {"name": name, "versions": [v.to_summary() for v in rows]}


@router.get("/{name}/versions/{version}")
async def get_version(
    name: str,
    version: int,
    versions: RecipeVersionService = Depends(_versions),
) -> dict:
    v = await versions.get(name, version)
    return v.to_full()


@router.post("/{name}/revert/{version}", response_model=RecipeSpec)
async def revert_version(
    name: str,
    version: int,
    body: RevertBody | None = None,
    lib: LibraryService = Depends(_lib),
    versions: RecipeVersionService = Depends(_versions),
) -> RecipeSpec:
    target = await versions.get(name, version)
    spec = lib.save_recipe_raw(name, target.yaml_text)
    await versions.record(
        name,
        target.yaml_text,
        source="revert",
        note=(body.note if body else None) or f"reverted to v{version}",
    )
    return spec
