from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sparkd.services.hf_catalog import HFCatalogService

router = APIRouter(prefix="/hf", tags=["hf"])


def _svc(request: Request) -> HFCatalogService:
    return request.app.state.hf


@router.get("/models/{model_id:path}")
async def get_hf_model(model_id: str, svc: HFCatalogService = Depends(_svc)) -> dict:
    info = await svc.fetch(model_id)
    return info.model_dump(mode="json")
