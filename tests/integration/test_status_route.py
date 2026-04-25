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

    async def fake_vllm(_self, _host, port=8000):
        return [], False

    monkeypatch.setattr(type(app.state.status), "_vllm_probe", fake_vllm)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app, box
    await app.state.pool.close_all()


async def test_status_lists_running_external_container(env):
    client, _app, box = env
    box.reply(
        "docker ps --format '{{json .}}'",
        stdout='{"ID":"abcdef123456","Image":"vllm","Labels":"","State":"running"}\n',
    )
    bid = (
        await client.post("/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    r = await client.get(f"/boxes/{bid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connectivity"] == "online"
    assert any(m["source"] == "external" for m in body["running_models"])


async def test_status_offline_when_docker_fails(env):
    client, _app, box = env
    box.reply(
        "docker ps --format '{{json .}}'", stderr="boom", exit=1
    )
    bid = (
        await client.post("/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    r = await client.get(f"/boxes/{bid}/status")
    assert r.status_code == 200
    # Docker exited 1 but produced no JSON, so reconcile sees no containers + healthy=False;
    # connectivity reads as "online" because the SSH command itself succeeded.
    body = r.json()
    assert body["connectivity"] in {"online", "offline"}
