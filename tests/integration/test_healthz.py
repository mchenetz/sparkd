import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.pool.close_all()


async def test_healthz_reports_components(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert "ssh_pool_size" in body
    assert "sparkd_home" in body
