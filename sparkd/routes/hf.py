from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sparkd.services.hf_catalog import HFCatalogService

router = APIRouter(prefix="/hf", tags=["hf"])


def _svc(request: Request) -> HFCatalogService:
    return request.app.state.hf


@router.get("/search")
async def search_models(
    q: str | None = None,
    pipeline_tag: str | None = None,
    library: str | None = None,
    sort: str = "trending_score",
    direction: int = -1,
    limit: int = 24,
    svc: HFCatalogService = Depends(_svc),
) -> dict:
    results = await svc.search(
        query=q,
        pipeline_tag=pipeline_tag,
        library=library,
        sort=sort,
        direction=direction,
        limit=limit,
    )
    return {"results": results, "count": len(results)}


@router.get("/models/{model_id:path}")
async def get_hf_model(model_id: str, svc: HFCatalogService = Depends(_svc)) -> dict:
    info = await svc.fetch(model_id)
    return info.model_dump(mode="json")
