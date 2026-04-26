"""UpstreamService — pulls from GitHub contents API and saves verbatim."""

import httpx
import pytest
import respx

from sparkd.schemas.upstream import UpstreamSyncRequest
from sparkd.services.library import LibraryService
from sparkd.services.upstream import UpstreamService


UPSTREAM_YAML = """recipe_version: 1
name: qwen3.5-35b-a3b-fp8
description: Qwen 3.5 FP8
model: org/qwen3.5-35b-fp8
defaults:
  tensor_parallel: 2
"""


def _contents_payload(filenames: list[str]) -> list[dict]:
    out = []
    for f in filenames:
        out.append(
            {
                "name": f,
                "type": "file",
                "download_url": f"https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/{f}",
            }
        )
    out.append({"name": "README.md", "type": "file", "download_url": "x"})
    out.append({"name": "3x-spark-cluster", "type": "dir"})
    return out


@pytest.fixture
def svc(sparkd_home):
    lib = LibraryService()
    return UpstreamService(library=lib), lib


@respx.mock
async def test_sync_imports_yaml_files_verbatim(svc):
    s, lib = svc
    respx.get(
        "https://api.github.com/repos/eugr/spark-vllm-docker/contents/recipes"
    ).mock(
        return_value=httpx.Response(200, json=_contents_payload(["recipe-a.yaml"]))
    )
    respx.get(
        "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/recipe-a.yaml"
    ).mock(return_value=httpx.Response(200, text=UPSTREAM_YAML))

    result = await s.sync(UpstreamSyncRequest())
    assert result.imported == ["recipe-a"]
    assert result.skipped == []
    assert result.errors == []
    # round-trip: bytes preserved
    assert lib.load_recipe_text("recipe-a") == UPSTREAM_YAML


@respx.mock
async def test_sync_skips_existing_unless_force(svc):
    s, lib = svc
    lib.save_recipe_raw("recipe-a", "name: recipe-a\nmodel: existing/m\n")
    respx.get(
        "https://api.github.com/repos/eugr/spark-vllm-docker/contents/recipes"
    ).mock(
        return_value=httpx.Response(200, json=_contents_payload(["recipe-a.yaml"]))
    )
    respx.get(
        "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/recipe-a.yaml"
    ).mock(return_value=httpx.Response(200, text=UPSTREAM_YAML))

    # First pass: skipped.
    r = await s.sync(UpstreamSyncRequest())
    assert r.imported == []
    assert r.skipped == ["recipe-a"]
    # local copy still has the existing model
    assert "existing/m" in lib.load_recipe_text("recipe-a")

    # With force=True the upstream version overwrites.
    r = await s.sync(UpstreamSyncRequest(force=True))
    assert r.imported == ["recipe-a"]
    assert lib.load_recipe_text("recipe-a") == UPSTREAM_YAML


@respx.mock
async def test_sync_records_errors_for_bad_yaml(svc):
    s, _lib = svc
    respx.get(
        "https://api.github.com/repos/eugr/spark-vllm-docker/contents/recipes"
    ).mock(
        return_value=httpx.Response(200, json=_contents_payload(["broken.yaml"]))
    )
    respx.get(
        "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/broken.yaml"
    ).mock(return_value=httpx.Response(200, text="- not\n- a\n- mapping\n"))

    r = await s.sync(UpstreamSyncRequest())
    assert r.imported == []
    assert len(r.errors) == 1
    assert r.errors[0].name == "broken"


@respx.mock
async def test_sync_skips_filenames_with_invalid_slugs(svc):
    s, _ = svc
    base = "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes"
    respx.get(
        "https://api.github.com/repos/eugr/spark-vllm-docker/contents/recipes"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "../sneaky.yaml",
                    "type": "file",
                    "download_url": f"{base}/sneaky.yaml",
                },
                {
                    "name": "ok.yaml",
                    "type": "file",
                    "download_url": f"{base}/ok.yaml",
                },
            ],
        )
    )
    respx.get(f"{base}/ok.yaml").mock(
        return_value=httpx.Response(200, text="name: ok\nmodel: a/b\n")
    )

    r = await s.sync(UpstreamSyncRequest())
    assert "ok" in r.imported
    assert any("sneaky" in e.name for e in r.errors)
