from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from sparkd import secrets as sparkd_secrets
from sparkd.errors import ValidationError
from sparkd.services.hf_catalog import HFCatalogService

router = APIRouter(prefix="/hf", tags=["hf"])


def _svc(request: Request) -> HFCatalogService:
    return request.app.state.hf


class HFTokenBody(BaseModel):
    token: str


@router.get("/token")
def get_token_status() -> dict:
    """Whether an HF token is saved (never returns the token itself)."""
    return {"configured": bool(sparkd_secrets.get_secret("hf_token"))}


@router.put("/token")
def put_token(body: HFTokenBody) -> dict:
    if not body.token.strip():
        raise ValidationError("token is required")
    sparkd_secrets.set_secret("hf_token", body.token.strip())
    return {"ok": True}


@router.delete("/token", status_code=204)
def delete_token() -> Response:
    sparkd_secrets.delete_secret("hf_token")
    return Response(status_code=204)


@router.get("/search")
async def search_models(
    q: str | None = None,
    pipeline_tag: str | None = None,
    library: str | None = None,
    sort: str = "downloads",
    direction: int = -1,
    limit: int = 24,
    svc: HFCatalogService = Depends(_svc),
) -> dict:
    results, error = await svc.search(
        query=q,
        pipeline_tag=pipeline_tag,
        library=library,
        sort=sort,
        direction=direction,
        limit=limit,
    )
    return {"results": results, "count": len(results), "error": error}


@router.get("/models/{model_id:path}")
async def get_hf_model(model_id: str, svc: HFCatalogService = Depends(_svc)) -> dict:
    info = await svc.fetch(model_id)
    return info.model_dump(mode="json")
