import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    await init_engine(create_all=True)

    async def fake_scan(*_args, **_kwargs):
        from sparkd.ssh.discovery import ProbeResult

        for r in [
            ProbeResult(
                host="127.0.0.1",
                port=22,
                reachable=True,
                is_dgx_spark=True,
                gpu_line="GB10",
            ),
            ProbeResult(host="127.0.0.2", port=22, reachable=False),
        ]:
            yield r

    monkeypatch.setattr("sparkd.routes.boxes.scan_subnet", fake_scan)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.pool.close_all()


async def test_discover_returns_job_id_then_results(client):
    r = await client.post(
        "/api/boxes/discover",
        json={"cidr": "127.0.0.0/30", "ssh_user": "ubuntu"},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    for _ in range(50):
        j = (await client.get(f"/api/jobs/{job_id}")).json()
        if j["state"] in {"succeeded", "failed"}:
            break
        await asyncio.sleep(0.02)
    assert j["state"] == "succeeded"
    assert any(p["is_dgx_spark"] for p in j["result"]["probes"])
