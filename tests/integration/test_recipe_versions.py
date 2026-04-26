"""Recipe versioning: every save appends a snapshot; revert restores."""

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
        yield c, app
    await app.state.pool.close_all()


async def test_create_records_v1(client):
    c, _app = client
    r = await c.post(
        "/api/recipes",
        json={"name": "r1", "model": "m", "args": {"--tp": "1"}},
    )
    assert r.status_code == 201
    rv = (await c.get("/api/recipes/r1/versions")).json()
    assert len(rv["versions"]) == 1
    assert rv["versions"][0]["version"] == 1
    assert rv["versions"][0]["source"] == "manual"


async def test_form_edit_appends_v2(client):
    c, _app = client
    await c.post("/api/recipes", json={"name": "r1", "model": "m"})
    await c.put(
        "/api/recipes/r1",
        json={
            "name": "r1",
            "model": "m",
            "description": "edited",
            "args": {"--tp": "2"},
            "env": {},
            "mods": [],
        },
    )
    rv = (await c.get("/api/recipes/r1/versions")).json()
    versions = sorted(rv["versions"], key=lambda v: v["version"])
    assert [v["version"] for v in versions] == [1, 2]


async def test_raw_edit_appends_with_source_raw(client):
    c, _app = client
    await c.post("/api/recipes", json={"name": "r1", "model": "m"})
    await c.put(
        "/api/recipes/r1/raw",
        json={"yaml": "name: r1\nmodel: x/y\n"},
    )
    rv = (await c.get("/api/recipes/r1/versions")).json()
    sources = [v["source"] for v in rv["versions"]]
    assert "raw" in sources


async def test_get_version_returns_yaml_text(client):
    c, _app = client
    await c.post("/api/recipes", json={"name": "r1", "model": "m"})
    rv = (await c.get("/api/recipes/r1/versions")).json()
    v1 = rv["versions"][0]["version"]
    full = (await c.get(f"/api/recipes/r1/versions/{v1}")).json()
    assert "yaml_text" in full
    assert "name: r1" in full["yaml_text"]


async def test_revert_restores_old_yaml_as_new_version(client):
    c, _app = client
    # v1: original
    await c.post(
        "/api/recipes",
        json={"name": "r1", "model": "m", "args": {"--tp": "1"}},
    )
    # v2: edited
    await c.put(
        "/api/recipes/r1",
        json={
            "name": "r1",
            "model": "m",
            "description": "edited",
            "args": {"--tp": "2"},
            "env": {},
            "mods": [],
        },
    )
    # revert to v1
    r = await c.post("/api/recipes/r1/revert/1", json={"note": "reverted"})
    assert r.status_code == 200
    # now there should be 3 versions and the latest YAML should resemble v1
    rv = (await c.get("/api/recipes/r1/versions")).json()
    assert len(rv["versions"]) == 3
    latest_version = max(v["version"] for v in rv["versions"])
    full = (await c.get(f"/api/recipes/r1/versions/{latest_version}")).json()
    assert "--tp: '1'" in full["yaml_text"] or "--tp: 1" in full["yaml_text"]
    assert full["source"] == "revert"


async def test_dedupe_when_save_yields_identical_yaml(client):
    """Saving the same content twice in a row shouldn't bump the version."""
    c, _app = client
    await c.post(
        "/api/recipes",
        json={"name": "r1", "model": "m", "args": {"--tp": "1"}},
    )
    body = {
        "name": "r1",
        "model": "m",
        "description": "",
        "args": {"--tp": "1"},
        "env": {},
        "mods": [],
    }
    await c.put("/api/recipes/r1", json=body)
    await c.put("/api/recipes/r1", json=body)
    rv = (await c.get("/api/recipes/r1/versions")).json()
    # v1 from create, v2 from first PUT, second PUT dedupes (same yaml).
    assert len(rv["versions"]) <= 2


async def test_delete_removes_versions(client):
    c, _app = client
    await c.post("/api/recipes", json={"name": "r1", "model": "m"})
    await c.delete("/api/recipes/r1")
    rv = (await c.get("/api/recipes/r1/versions")).json()
    assert rv["versions"] == []
