from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from sparkd.errors import ValidationError
from sparkd.schemas.recipe import RecipeSpec
from sparkd.schemas.upstream import UpstreamSyncRequest, UpstreamSyncResult
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.services.upstream import UpstreamService


class RecipeRawBody(BaseModel):
    yaml: str


class RecipeRawResponse(BaseModel):
    yaml: str
    name: str

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _lib(request: Request) -> LibraryService:
    return request.app.state.library


def _rs(request: Request) -> RecipeService:
    return request.app.state.recipes


def _upstream(request: Request) -> UpstreamService:
    return request.app.state.upstream


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
def create_recipe(spec: RecipeSpec, lib: LibraryService = Depends(_lib)) -> RecipeSpec:
    lib.save_recipe(spec)
    return spec


@router.get("/{name}", response_model=RecipeSpec)
def get_recipe(
    name: str, box: str | None = None, lib: LibraryService = Depends(_lib)
) -> RecipeSpec:
    return lib.load_recipe(name, box_id=box)


@router.put("/{name}", response_model=RecipeSpec)
def put_recipe(
    name: str, spec: RecipeSpec, lib: LibraryService = Depends(_lib)
) -> RecipeSpec:
    if spec.name != name:
        raise ValidationError("path name and body name disagree")
    # Preserve upstream-format fields (defaults/command/container/...) when
    # editing an existing recipe via the form view.
    lib.update_recipe(spec)
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
def put_recipe_raw(
    name: str, body: RecipeRawBody, lib: LibraryService = Depends(_lib)
) -> RecipeSpec:
    return lib.save_recipe_raw(name, body.yaml)


@router.delete("/{name}", status_code=204)
def delete_recipe(name: str, lib: LibraryService = Depends(_lib)) -> Response:
    lib.delete_recipe(name)
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
