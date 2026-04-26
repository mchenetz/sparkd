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
async def test_get_hf_model_missing_returns_minimal(client):
    respx.get("https://huggingface.co/api/models/missing/x").mock(
        return_value=httpx.Response(404, json={})
    )
    r = await client.get("/api/hf/models/missing/x")
    assert r.status_code == 200
    assert r.json()["id"] == "missing/x"
