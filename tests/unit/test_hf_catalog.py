import httpx
import pytest
import respx

from sparkd.services.hf_catalog import HFCatalogService


@pytest.fixture
def svc(sparkd_home):
    return HFCatalogService()


@respx.mock
async def test_fetch_returns_parsed_info(svc):
    respx.get("https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "meta-llama/Llama-3.1-8B-Instruct",
                "pipeline_tag": "text-generation",
                "license": "llama3.1",
                "config": {
                    "architectures": ["LlamaForCausalLM"],
                    "max_position_embeddings": 131072,
                    "torch_dtype": "bfloat16",
                },
                "safetensors": {"total": 8030261248},
            },
        )
    )
    info = await svc.fetch("meta-llama/Llama-3.1-8B-Instruct")
    assert info.architecture == "LlamaForCausalLM"
    assert info.context_length == 131072
    assert "bf16" in info.supported_dtypes
    # safetensors/2/1e9 ≈ 4.015 — represents byte-to-param estimate
    assert info.parameters_b > 0


@respx.mock
async def test_fetch_returns_cache_hit_within_ttl(svc):
    route = respx.get("https://huggingface.co/api/models/x/y").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "x/y",
                "config": {"architectures": ["A"]},
                "safetensors": {"total": 1_000_000_000},
            },
        )
    )
    a = await svc.fetch("x/y")
    b = await svc.fetch("x/y")
    assert a == b
    assert route.call_count == 1


@respx.mock
async def test_fetch_404_returns_minimal_info(svc):
    respx.get("https://huggingface.co/api/models/missing/x").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    info = await svc.fetch("missing/x")
    assert info.id == "missing/x"
    assert info.architecture == ""
