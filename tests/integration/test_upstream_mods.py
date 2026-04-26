"""UpstreamService.sync_mods walks each mod directory and saves all files."""

import httpx
import pytest
import respx

from sparkd.schemas.upstream import UpstreamSyncRequest
from sparkd.services.library import LibraryService
from sparkd.services.mod import ModService
from sparkd.services.upstream import UpstreamService


@pytest.fixture
def svc(sparkd_home):
    lib = LibraryService()
    mods = ModService()
    return UpstreamService(library=lib, mods=mods), mods


def _file_entry(repo: str, branch: str, path: str) -> dict:
    return {
        "type": "file",
        "name": path.rsplit("/", 1)[-1],
        "path": path,
        "download_url": f"https://raw.githubusercontent.com/{repo}/{branch}/{path}",
    }


@respx.mock
async def test_sync_mods_fetches_all_files_and_saves(svc):
    s, mods = svc
    repo = "eugr/spark-vllm-docker"
    branch = "main"
    # /contents/mods → two dirs
    respx.get(f"https://api.github.com/repos/{repo}/contents/mods").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"type": "dir", "name": "fix-qwen", "path": "mods/fix-qwen"},
                {"type": "dir", "name": "drop-caches", "path": "mods/drop-caches"},
            ],
        )
    )
    # /contents/mods/fix-qwen → two files
    respx.get(f"https://api.github.com/repos/{repo}/contents/mods/fix-qwen").mock(
        return_value=httpx.Response(
            200,
            json=[
                _file_entry(repo, branch, "mods/fix-qwen/run.sh"),
                _file_entry(repo, branch, "mods/fix-qwen/transformers.patch"),
            ],
        )
    )
    # /contents/mods/drop-caches → one file
    respx.get(f"https://api.github.com/repos/{repo}/contents/mods/drop-caches").mock(
        return_value=httpx.Response(
            200,
            json=[_file_entry(repo, branch, "mods/drop-caches/hook.sh")],
        )
    )
    # raw downloads
    respx.get(
        f"https://raw.githubusercontent.com/{repo}/{branch}/mods/fix-qwen/run.sh"
    ).mock(return_value=httpx.Response(200, text="#!/bin/sh\necho qwen\n"))
    respx.get(
        f"https://raw.githubusercontent.com/{repo}/{branch}/mods/fix-qwen/transformers.patch"
    ).mock(return_value=httpx.Response(200, text="--- a\n+++ b\n"))
    respx.get(
        f"https://raw.githubusercontent.com/{repo}/{branch}/mods/drop-caches/hook.sh"
    ).mock(return_value=httpx.Response(200, text="#!/bin/sh\nsync; echo 3 > /proc/sys/vm/drop_caches\n"))

    result = await s.sync_mods(UpstreamSyncRequest())
    assert sorted(result.imported) == ["drop-caches", "fix-qwen"]
    assert result.errors == []
    fix = mods.load("fix-qwen")
    assert "run.sh" in fix.files
    assert fix.files["run.sh"].startswith("#!/bin/sh")
    assert "transformers.patch" in fix.files


@respx.mock
async def test_sync_mods_skips_existing_unless_force(svc):
    s, mods = svc
    repo = "eugr/spark-vllm-docker"
    from sparkd.schemas.mod import ModSpec

    mods.save(ModSpec(name="alpha", target_models=[], files={"x": "y"}))

    respx.get(f"https://api.github.com/repos/{repo}/contents/mods").mock(
        return_value=httpx.Response(
            200, json=[{"type": "dir", "name": "alpha", "path": "mods/alpha"}]
        )
    )
    respx.get(f"https://api.github.com/repos/{repo}/contents/mods/alpha").mock(
        return_value=httpx.Response(
            200, json=[_file_entry(repo, "main", "mods/alpha/run.sh")]
        )
    )
    respx.get(
        f"https://raw.githubusercontent.com/{repo}/main/mods/alpha/run.sh"
    ).mock(return_value=httpx.Response(200, text="from-upstream"))

    r = await s.sync_mods(UpstreamSyncRequest())
    assert r.skipped == ["alpha"]
    assert r.imported == []

    r = await s.sync_mods(UpstreamSyncRequest(force=True))
    assert r.imported == ["alpha"]
    assert mods.load("alpha").files["run.sh"] == "from-upstream"
