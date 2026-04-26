import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.pool.close_all()


async def test_create_list_get_delete_mod(client):
    body = {
        "name": "patch-a",
        "target_models": ["llama"],
        "description": "fix vocab",
        "files": {"patch.diff": "--- a\n+++ b\n"},
        "enabled": True,
    }
    r = await client.post("/api/mods", json=body)
    assert r.status_code == 201
    r = await client.get("/api/mods")
    assert r.status_code == 200
    assert any(m["name"] == "patch-a" for m in r.json())
    r = await client.get("/api/mods/patch-a")
    assert r.status_code == 200
    assert r.json()["files"]["patch.diff"].startswith("--- a")
    r = await client.delete("/api/mods/patch-a")
    assert r.status_code == 204
    assert (await client.get("/api/mods/patch-a")).status_code == 404


async def test_create_mod_invalid_name_returns_422(client):
    r = await client.post(
        "/api/mods",
        json={"name": "../evil", "target_models": [], "files": {}},
    )
    assert r.status_code == 422
