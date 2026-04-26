from __future__ import annotations

import re

import httpx

from sparkd.errors import UpstreamError
from sparkd.schemas.upstream import (
    UpstreamSyncError,
    UpstreamSyncRequest,
    UpstreamSyncResult,
)
from sparkd.services.library import LibraryService

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")


class UpstreamService:
    """Pull recipes from a public GitHub repo's `recipes/` directory.

    Designed for eugr/spark-vllm-docker but works for any repo with the same
    layout. Files are saved verbatim (raw YAML) so they round-trip byte-identical
    when later synced to a box.
    """

    def __init__(self, library: LibraryService) -> None:
        self.library = library

    async def sync(self, req: UpstreamSyncRequest) -> UpstreamSyncResult:
        result = UpstreamSyncResult(repo=req.repo, branch=req.branch)
        contents = await self._list_contents(req.repo, req.branch)
        async with httpx.AsyncClient(timeout=20.0) as client:
            for entry in contents:
                if entry.get("type") != "file":
                    continue
                fname = entry.get("name", "")
                if not (fname.endswith(".yaml") or fname.endswith(".yml")):
                    continue
                stem = fname.rsplit(".", 1)[0]
                if not _NAME_RE.match(stem):
                    result.errors.append(
                        UpstreamSyncError(
                            name=fname, message="filename not a valid recipe slug"
                        )
                    )
                    continue
                if not req.force and self.library.has_recipe(stem):
                    result.skipped.append(stem)
                    continue
                download_url = entry.get("download_url")
                if not download_url:
                    result.errors.append(
                        UpstreamSyncError(name=stem, message="no download_url")
                    )
                    continue
                try:
                    raw = await client.get(download_url)
                except httpx.HTTPError as exc:
                    result.errors.append(
                        UpstreamSyncError(name=stem, message=f"fetch failed: {exc}")
                    )
                    continue
                if raw.status_code != 200:
                    result.errors.append(
                        UpstreamSyncError(
                            name=stem, message=f"fetch http {raw.status_code}"
                        )
                    )
                    continue
                try:
                    self.library.save_recipe_raw(stem, raw.text)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(
                        UpstreamSyncError(name=stem, message=str(exc))
                    )
                    continue
                result.imported.append(stem)
        return result

    async def _list_contents(self, repo: str, branch: str) -> list[dict]:
        url = f"https://api.github.com/repos/{repo}/contents/recipes"
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                r = await client.get(
                    url,
                    params={"ref": branch},
                    headers={"Accept": "application/vnd.github+json"},
                )
            except httpx.HTTPError as exc:
                raise UpstreamError(f"github: {exc}") from exc
        if r.status_code == 404:
            raise UpstreamError(f"repo or branch not found: {repo}@{branch}")
        if r.status_code != 200:
            raise UpstreamError(
                f"github contents api returned {r.status_code}: {r.text[:200]}"
            )
        body = r.json()
        if not isinstance(body, list):
            raise UpstreamError("github contents api returned non-list response")
        return body
