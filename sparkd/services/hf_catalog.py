from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from sparkd.schemas.hf import HFModelInfo

_TTL = timedelta(hours=24)


def _normalize_dtype(t: str) -> str:
    s = (t or "").lower()
    if s in {"bfloat16", "bf16"}:
        return "bf16"
    if s in {"float16", "fp16", "half"}:
        return "fp16"
    if s in {"float32", "fp32"}:
        return "fp32"
    return s


class HFCatalogService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[datetime, HFModelInfo]] = {}

    async def fetch(self, model_id: str) -> HFModelInfo:
        now = datetime.now(timezone.utc)
        cached = self._cache.get(model_id)
        if cached and now - cached[0] < _TTL:
            return cached[1]
        info = await self._fetch_remote(model_id, now)
        self._cache[model_id] = (now, info)
        return info

    async def search(
        self,
        *,
        query: str | None = None,
        pipeline_tag: str | None = None,
        library: str | None = None,
        sort: str = "trending_score",
        direction: int = -1,
        limit: int = 24,
    ) -> list[dict]:
        """Search Hugging Face Hub for models. Returns lightweight summaries
        suitable for a list/browser UI: id, downloads, likes, lastModified,
        pipeline_tag, tags, library_name."""
        params: dict[str, str | int] = {
            "limit": max(1, min(int(limit), 100)),
            "sort": sort,
            "direction": direction,
        }
        if query:
            params["search"] = query
        # The HF API accepts repeated `filter=` for AND-ing — we only filter
        # by one tag at a time so a single value is fine.
        filters: list[str] = []
        if pipeline_tag:
            filters.append(pipeline_tag)
        if library:
            filters.append(library)
        url = "https://huggingface.co/api/models"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(
                    url,
                    params=[*params.items(), *(("filter", f) for f in filters)],
                )
            except httpx.HTTPError:
                return []
        if r.status_code != 200:
            return []
        body = r.json()
        if not isinstance(body, list):
            return []
        out: list[dict] = []
        for entry in body:
            out.append(
                {
                    "id": entry.get("modelId") or entry.get("id") or "",
                    "downloads": entry.get("downloads") or 0,
                    "likes": entry.get("likes") or 0,
                    "last_modified": entry.get("lastModified")
                    or entry.get("last_modified"),
                    "pipeline_tag": entry.get("pipeline_tag") or "",
                    "library_name": entry.get("library_name") or "",
                    "tags": entry.get("tags") or [],
                    "private": bool(entry.get("private")),
                    "gated": entry.get("gated") or False,
                }
            )
        return out

    async def _fetch_remote(self, model_id: str, now: datetime) -> HFModelInfo:
        url = f"https://huggingface.co/api/models/{model_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.get(url)
            except httpx.HTTPError:
                return HFModelInfo(id=model_id, fetched_at=now)
        if r.status_code != 200:
            return HFModelInfo(id=model_id, fetched_at=now)
        body = r.json()
        config = body.get("config", {}) or {}
        archs = config.get("architectures") or []
        architecture = archs[0] if archs else ""
        ctx_len = int(
            config.get("max_position_embeddings")
            or config.get("max_seq_len")
            or 0
        )
        dtypes_raw = config.get("torch_dtype") or ""
        if isinstance(dtypes_raw, str) and dtypes_raw:
            dtypes = [_normalize_dtype(dtypes_raw)]
        else:
            dtypes = []
        params_b = 0.0
        ssft = body.get("safetensors") or {}
        total_bytes = int(ssft.get("total") or 0)
        if total_bytes:
            params_b = round(total_bytes / 2 / 1e9, 2)
        return HFModelInfo(
            id=model_id,
            architecture=architecture,
            parameters_b=params_b,
            context_length=ctx_len,
            supported_dtypes=dtypes,
            license=body.get("license", "") or "",
            pipeline_tag=body.get("pipeline_tag", "") or "",
            fetched_at=now,
        )
