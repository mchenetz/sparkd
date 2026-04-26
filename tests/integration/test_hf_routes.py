import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    # Avoid real keyring lookups during build_app.
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.pool.close_all()


@respx.mock
async def test_get_hf_model_returns_facts(client):
    respx.get("https://huggingface.co/api/models/x/y").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "x/y",
                "pipeline_tag": "text-generation",
                "config": {"architectures": ["A"], "max_position_embeddings": 4096},
                "safetensors": {"total": 2_000_000_000},
            },
        )
    )
    r = await client.get("/api/hf/models/x/y")
    assert r.status_code == 200
    body = r.json()
    assert body["architecture"] == "A"
    assert body["context_length"] == 4096


@respx.mock
async def test_search_returns_summaries(client):
    respx.get("https://huggingface.co/api/models").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "modelId": "meta-llama/Llama-3.1-8B-Instruct",
                    "downloads": 1234567,
                    "likes": 8000,
                    "lastModified": "2026-04-20T00:00:00Z",
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["llama", "text-generation"],
                },
                {
                    "modelId": "Qwen/Qwen2.5-72B-Instruct",
                    "downloads": 999999,
                    "likes": 5500,
                    "lastModified": "2026-04-19T00:00:00Z",
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["qwen"],
                },
            ],
        )
    )
    r = await client.get("/api/hf/search?q=llama&pipeline_tag=text-generation&limit=24")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["error"] is None
    assert body["results"][0]["id"] == "meta-llama/Llama-3.1-8B-Instruct"
    assert body["results"][0]["pipeline_tag"] == "text-generation"


@respx.mock
async def test_search_handles_upstream_error(client):
    respx.get("https://huggingface.co/api/models").mock(
        return_value=httpx.Response(503, text="upstream gone")
    )
    r = await client.get("/api/hf/search?q=x")
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert body["count"] == 0
    assert body["error"]
    assert "503" in body["error"]


async def test_token_storage_endpoints(client, monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        "sparkd.secrets._backend_set",
        lambda svc, k, v: store.__setitem__((svc, k), v),
    )
    monkeypatch.setattr(
        "sparkd.secrets._backend_get", lambda svc, k: store.get((svc, k))
    )
    monkeypatch.setattr(
        "sparkd.secrets._backend_delete",
        lambda svc, k: store.pop((svc, k), None),
    )
    # initial: not configured
    assert (await client.get("/api/hf/token")).json() == {"configured": False}
    # save
    r = await client.put("/api/hf/token", json={"token": "hf_xxx"})
    assert r.status_code == 200
    assert store[("sparkd", "hf_token")] == "hf_xxx"
    assert (await client.get("/api/hf/token")).json() == {"configured": True}
    # clear
    assert (await client.delete("/api/hf/token")).status_code == 204
    assert (await client.get("/api/hf/token")).json() == {"configured": False}


@respx.mock
async def test_get_hf_model_missing_returns_minimal(client):
    respx.get("https://huggingface.co/api/models/missing/x").mock(
        return_value=httpx.Response(404, json={})
    )
    r = await client.get("/api/hf/models/missing/x")
    assert r.status_code == 200
    assert r.json()["id"] == "missing/x"
