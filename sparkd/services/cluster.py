from __future__ import annotations


class ClusterService:
    async def launch_across(self, *, boxes: list[str], recipe: str) -> None:
        raise NotImplementedError("multi-box cluster orchestration is v2")

    async def topology(self) -> dict:
        return {"nodes": [], "edges": []}
