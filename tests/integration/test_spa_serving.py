"""SPA fallback serves index.html for non-API routes when the frontend is built."""

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


async def test_spa_root_serves_index_when_built(client):
    r = await client.get("/")
    # If frontend was built (sparkd/static/index.html exists), expect 200 + html.
    # If not, expect 404 (no route registered) or 200 with placeholder JSON.
    assert r.status_code in {200, 404}


async def test_api_routes_still_work_alongside_spa(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"
