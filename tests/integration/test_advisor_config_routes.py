"""Provider catalog and active-config endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
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
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app, store
    await app.state.pool.close_all()


async def test_providers_catalog_includes_known_families(client):
    c, _app, _store = client
    body = (await c.get("/api/advisor/providers")).json()
    ids = {p["id"] for p in body["providers"]}
    assert {"anthropic", "openai", "gemini", "mistral", "groq", "vllm"} <= ids
    vllm = next(p for p in body["providers"] if p["id"] == "vllm")
    assert vllm["requires_key"] is False
    assert vllm["base_url_editable"] is True
    assert vllm["family"] == "openai_compat"


async def test_put_config_anthropic_persists_and_activates(client):
    c, app, store = client
    r = await c.put(
        "/api/advisor/config",
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "api_key": "sk-ant-test",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_provider"] == "anthropic"
    assert body["active_model"] == "claude-sonnet-4-6"
    assert store[("sparkd", "anthropic_api_key")] == "sk-ant-test"
    # status reflects new state
    s = (await c.get("/api/advisor/status")).json()
    assert s["configured"] is True
    assert s["active_provider"] == "anthropic"


async def test_put_config_vllm_does_not_require_key(client):
    c, _app, _store = client
    r = await c.put(
        "/api/advisor/config",
        json={
            "provider": "vllm",
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "base_url": "http://localhost:9999/v1",
        },
    )
    assert r.status_code == 200
    s = (await c.get("/api/advisor/status")).json()
    assert s["configured"] is True
    assert s["active_provider"] == "vllm"


async def test_put_config_openai_requires_key_when_none_saved(client):
    c, _app, _store = client
    r = await c.put(
        "/api/advisor/config",
        json={"provider": "openai", "model": "gpt-4o"},
    )
    assert r.status_code == 422


async def test_put_config_unknown_provider_404(client):
    c, _app, _store = client
    r = await c.put(
        "/api/advisor/config",
        json={"provider": "made-up", "model": "x"},
    )
    assert r.status_code == 404


async def test_legacy_setup_still_works(client):
    c, _app, store = client
    r = await c.post(
        "/api/advisor/setup", json={"anthropic_api_key": "sk-ant-legacy"}
    )
    assert r.status_code == 200
    assert store[("sparkd", "anthropic_api_key")] == "sk-ant-legacy"
    s = (await c.get("/api/advisor/status")).json()
    assert s["active_provider"] == "anthropic"
