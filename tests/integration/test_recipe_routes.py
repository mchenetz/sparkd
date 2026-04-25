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


async def test_create_and_list_recipe(client):
    body = {"name": "r1", "model": "m", "args": {"--tp": "1"}}
    assert (await client.post("/recipes", json=body)).status_code == 201
    rs = (await client.get("/recipes")).json()
    assert rs[0]["name"] == "r1"


async def test_get_missing_recipe_404(client):
    r = await client.get("/recipes/nope")
    assert r.status_code == 404


async def test_delete_recipe(client):
    await client.post("/recipes", json={"name": "r1", "model": "m"})
    assert (await client.delete("/recipes/r1")).status_code == 204
    assert (await client.get("/recipes/r1")).status_code == 404
