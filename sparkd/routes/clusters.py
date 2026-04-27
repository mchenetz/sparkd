"""Cluster = group of boxes sharing a `cluster` tag value."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sparkd.errors import NotFoundError
from sparkd.services.box import BoxService

router = APIRouter(prefix="/clusters", tags=["clusters"])


def _svc(request: Request) -> BoxService:
    return request.app.state.boxes


def _aggregate(boxes: list) -> dict:
    """Roll up per-node caps into a cluster-wide summary using the cached
    capabilities on each Box row. Empty/None values are skipped."""
    total_gpus = 0
    aggregate_vram = 0
    gpu_models: set[str] = set()
    ib: set[str] = set()
    for b in boxes:
        # b is a BoxSpec; the cached `capabilities_json` is on the ORM row,
        # not the spec, so we can't aggregate here without a DB hit. Caller
        # passes already-prepared dicts when finer aggregation is needed.
        _ = b
    return {
        "node_count": len(boxes),
        "total_gpus": total_gpus,
        "aggregate_vram_gb": aggregate_vram,
        "gpu_models": sorted(gpu_models),
        "ib_interfaces": sorted(ib),
    }


@router.get("")
async def list_clusters(svc: BoxService = Depends(_svc)) -> dict:
    grouped = await svc.list_clusters()
    return {
        "clusters": [
            {
                "name": name,
                "box_count": len(boxes),
                "boxes": [b.model_dump(mode="json") for b in boxes],
            }
            for name, boxes in sorted(grouped.items())
        ]
    }


@router.get("/{name}")
async def get_cluster(name: str, svc: BoxService = Depends(_svc)) -> dict:
    grouped = await svc.list_clusters()
    if name not in grouped:
        raise NotFoundError("cluster", name)
    boxes = grouped[name]
    return {
        "name": name,
        "box_count": len(boxes),
        "boxes": [b.model_dump(mode="json") for b in boxes],
    }
