import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.ssh.pool import SSHTarget


@pytest.fixture
async def env(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()
    box, port = fake_box
    monkeypatch.setattr(
        type(app.state.boxes),
        "_target_for",
        lambda _self, _row: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )

    async def fake_validate(_self, _spec, _box_id, *, cluster=None):
        return []

    monkeypatch.setattr(type(app.state.recipes), "validate", fake_validate)

    async def fake_sync(_self, *_a, **_k):
        return None

    monkeypatch.setattr(type(app.state.launches), "_sync_files", fake_sync)
    box.set_default(stdout="12345\n", exit=0)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app, box
    await app.state.pool.close_all()


async def test_launch_creates_record(env):
    client, _app, _box = env
    bid = (
        await client.post("/api/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    await client.post("/api/recipes", json={"name": "r1", "model": "m"})
    r = await client.post("/api/launches", json={"recipe": "r1", "target": bid})
    assert r.status_code == 201
    assert r.json()["state"] == "starting"


async def test_launch_route_accepts_cluster_target(env):
    client, _app, _box = env
    h = (
        await client.post(
            "/api/boxes",
            json={
                "name": "n1",
                "host": "10.0.0.1",
                "user": "u",
                "tags": {"cluster": "alpha"},
            },
        )
    ).json()
    await client.post(
        "/api/boxes",
        json={
            "name": "n2",
            "host": "10.0.0.2",
            "user": "u",
            "tags": {"cluster": "alpha"},
        },
    )
    await client.post("/api/recipes", json={"name": "r1", "model": "m"})
    r = await client.post(
        "/api/launches", json={"recipe": "r1", "target": "cluster:alpha"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["box_id"] == h["id"]
    assert body["cluster_name"] == "alpha"
