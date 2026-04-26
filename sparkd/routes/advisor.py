from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from sparkd import secrets as sparkd_secrets
from sparkd.advisor import AnthropicAdapter
from sparkd.errors import ValidationError
from sparkd.hardware import default_dgx_spark_caps
from sparkd.schemas.advisor import AdvisorSession
from sparkd.schemas.box import BoxCapabilities
from sparkd.services.advisor import AdvisorService
from sparkd.services.box import BoxService
from sparkd.services.hf_catalog import HFCatalogService
from sparkd.services.library import LibraryService

router = APIRouter(prefix="/advisor", tags=["advisor"])


def _svc(request: Request) -> AdvisorService:
    return request.app.state.advisor


def _hf(request: Request) -> HFCatalogService:
    return request.app.state.hf


def _boxes(request: Request) -> BoxService:
    return request.app.state.boxes


def _lib(request: Request) -> LibraryService:
    return request.app.state.library


async def _resolve_caps(
    target_box_id: str | None, boxes: BoxService
) -> BoxCapabilities:
    """Use real box capabilities when available, else canonical DGX Spark defaults."""
    if not target_box_id:
        return default_dgx_spark_caps()
    try:
        return await boxes.capabilities(target_box_id)
    except Exception:  # noqa: BLE001  — degrade gracefully
        return default_dgx_spark_caps()


class CreateSessionBody(BaseModel):
    kind: str
    target_box_id: str | None = None
    target_recipe_name: str | None = None
    hf_model_id: str | None = None


class CreateSessionResponse(BaseModel):
    id: str


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionBody, svc: AdvisorService = Depends(_svc)
) -> CreateSessionResponse:
    if body.kind not in {"recipe", "optimize", "mod"}:
        raise ValidationError(f"invalid kind: {body.kind!r}")
    sid = await svc.create_session(
        kind=body.kind,
        target_box_id=body.target_box_id,
        target_recipe_name=body.target_recipe_name,
        hf_model_id=body.hf_model_id,
    )
    return CreateSessionResponse(id=sid)


@router.get("/sessions/{session_id}", response_model=AdvisorSession)
async def get_session(
    session_id: str, svc: AdvisorService = Depends(_svc)
) -> AdvisorSession:
    return await svc.get_session(session_id)


class GenerateRecipeBody(BaseModel):
    user_msg: str | None = None


@router.post("/sessions/{session_id}/recipe")
async def generate_recipe(
    session_id: str,
    body: GenerateRecipeBody,
    svc: AdvisorService = Depends(_svc),
    hf: HFCatalogService = Depends(_hf),
    boxes: BoxService = Depends(_boxes),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.hf_model_id:
        raise ValidationError("session has no hf_model_id")
    info = await hf.fetch(sess.hf_model_id)
    caps = await _resolve_caps(sess.target_box_id, boxes)
    draft = None
    deltas: list[str] = []
    async for ev in svc.generate_recipe(
        session_id, info=info, caps=caps, user_msg=body.user_msg
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}


class OptimizeBody(BaseModel):
    goals: list[str] = Field(default_factory=list)
    user_msg: str | None = None


@router.post("/sessions/{session_id}/optimize")
async def optimize_recipe(
    session_id: str,
    body: OptimizeBody,
    svc: AdvisorService = Depends(_svc),
    boxes: BoxService = Depends(_boxes),
    lib: LibraryService = Depends(_lib),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.target_recipe_name:
        raise ValidationError("session needs target_recipe_name")
    recipe = lib.load_recipe(sess.target_recipe_name, box_id=sess.target_box_id)
    caps = await _resolve_caps(sess.target_box_id, boxes)
    draft = None
    deltas: list[str] = []
    async for ev in svc.optimize_recipe(
        session_id,
        recipe=recipe,
        caps=caps,
        goals=body.goals,
        user_msg=body.user_msg,
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}


class ProposeModBody(BaseModel):
    error_log: str
    user_msg: str | None = None


@router.post("/sessions/{session_id}/mod")
async def propose_mod(
    session_id: str,
    body: ProposeModBody,
    svc: AdvisorService = Depends(_svc),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.hf_model_id:
        raise ValidationError("session has no hf_model_id")
    draft = None
    deltas: list[str] = []
    async for ev in svc.propose_mod(
        session_id,
        error_log=body.error_log,
        model_id=sess.hf_model_id,
        user_msg=body.user_msg,
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}


class SetupBody(BaseModel):
    anthropic_api_key: str


@router.post("/setup")
def setup(body: SetupBody, request: Request) -> dict:
    if not body.anthropic_api_key.strip():
        raise ValidationError("anthropic_api_key is required")
    key = body.anthropic_api_key.strip()
    sparkd_secrets.set_secret("anthropic_api_key", key)
    request.app.state.advisor.port = AnthropicAdapter(api_key=key)
    return {"ok": True}


@router.get("/status")
def status(request: Request) -> dict:
    port = getattr(request.app.state.advisor, "port", None)
    return {"configured": port is not None}
