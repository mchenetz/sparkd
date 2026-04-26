from __future__ import annotations

import re
from collections import defaultdict

import httpx

from sparkd.errors import UpstreamError
from sparkd.schemas.mod import ModSpec
from sparkd.schemas.upstream import (
    UpstreamSyncError,
    UpstreamSyncRequest,
    UpstreamSyncResult,
)
from sparkd.services.library import LibraryService
from sparkd.services.mod import ModService

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")


class UpstreamService:
    """Pull recipes from a public GitHub repo's `recipes/` directory.

    Designed for eugr/spark-vllm-docker but works for any repo with the same
    layout. Files are saved verbatim (raw YAML) so they round-trip byte-identical
    when later synced to a box.
    """

    def __init__(self, library: LibraryService, mods: ModService | None = None) -> None:
        self.library = library
        self.mods = mods or ModService()

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
        return await self._contents(repo, branch, "recipes")

    async def _contents(self, repo: str, branch: str, path: str) -> list[dict]:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
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
            raise UpstreamError(f"path not found: {repo}@{branch}:{path}")
        if r.status_code != 200:
            raise UpstreamError(
                f"github contents api returned {r.status_code}: {r.text[:200]}"
            )
        body = r.json()
        if not isinstance(body, list):
            raise UpstreamError("github contents api returned non-list response")
        return body

    async def sync_mods(self, req: UpstreamSyncRequest) -> UpstreamSyncResult:
        """Pull all mods from `mods/` (each mod is a directory with arbitrary files)."""
        result = UpstreamSyncResult(repo=req.repo, branch=req.branch)
        try:
            top = await self._contents(req.repo, req.branch, "mods")
        except UpstreamError:
            raise
        async with httpx.AsyncClient(timeout=30.0) as client:
            for entry in top:
                if entry.get("type") != "dir":
                    continue
                name = entry.get("name", "")
                if not _NAME_RE.match(name):
                    result.errors.append(
                        UpstreamSyncError(
                            name=name, message="dirname not a valid mod slug"
                        )
                    )
                    continue
                if not req.force and self._mod_exists(name):
                    result.skipped.append(name)
                    continue
                try:
                    files = await self._fetch_mod_files(
                        client, req.repo, req.branch, name
                    )
                except UpstreamError as exc:
                    result.errors.append(
                        UpstreamSyncError(name=name, message=str(exc))
                    )
                    continue
                if not files:
                    result.errors.append(
                        UpstreamSyncError(name=name, message="no files found")
                    )
                    continue
                spec = ModSpec(
                    name=name,
                    target_models=[],
                    description=f"Imported from {req.repo}@{req.branch}",
                    files=files,
                    enabled=True,
                )
                try:
                    self.mods.save(spec)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(
                        UpstreamSyncError(name=name, message=str(exc))
                    )
                    continue
                result.imported.append(name)
        return result

    def _mod_exists(self, name: str) -> bool:
        from sparkd import paths
        return (paths.library() / "mods" / name / "mod.yaml").exists()

    async def _fetch_mod_files(
        self, client: httpx.AsyncClient, repo: str, branch: str, mod_name: str
    ) -> dict[str, str]:
        """Walk a mod directory recursively and return {relative_path: content}."""
        files: dict[str, str] = {}
        # Stack of paths to walk, relative to mods/
        stack: list[str] = [mod_name]
        seen: set[str] = set()
        while stack:
            sub = stack.pop()
            if sub in seen:
                continue
            seen.add(sub)
            entries = await self._contents(repo, branch, f"mods/{sub}")
            for e in entries:
                etype = e.get("type")
                ename = e.get("name", "")
                if etype == "dir":
                    stack.append(f"{sub}/{ename}")
                    continue
                if etype != "file":
                    continue
                # Skip unsafe path components
                if ".." in ename or ename.startswith("/"):
                    continue
                rel = f"{sub}/{ename}".removeprefix(f"{mod_name}/")
                if rel == mod_name:  # the dir itself
                    continue
                if not rel:
                    continue
                durl = e.get("download_url")
                if not durl:
                    continue
                try:
                    r = await client.get(durl)
                except httpx.HTTPError as exc:
                    raise UpstreamError(f"fetch {rel}: {exc}") from exc
                if r.status_code != 200:
                    raise UpstreamError(f"fetch {rel}: http {r.status_code}")
                files[rel] = r.text
        return files
