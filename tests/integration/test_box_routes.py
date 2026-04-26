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


async def test_create_then_list_box(client):
    resp = await client.post(
        "/api/boxes",
        json={"name": "spark-01", "host": "10.0.0.5", "user": "ubuntu"},
    )
    assert resp.status_code == 201
    box_id = resp.json()["id"]
    resp = await client.get("/api/boxes")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == box_id


async def test_get_missing_returns_404_problem(client):
    resp = await client.get("/api/boxes/nope")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_update_box_changes_connection_details(client):
    bid = (
        await client.post(
            "/api/boxes",
            json={"name": "spark-01", "host": "10.0.0.5", "user": "ubuntu"},
        )
    ).json()["id"]
    r = await client.put(
        f"/api/boxes/{bid}",
        json={
            "name": "spark-01-renamed",
            "host": "10.0.0.6",
            "port": 2222,
            "user": "ec2-user",
            "use_agent": True,
            "repo_path": "/opt/spark-vllm-docker",
            "tags": {"env": "prod"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "spark-01-renamed"
    assert body["host"] == "10.0.0.6"
    assert body["port"] == 2222
    assert body["repo_path"] == "/opt/spark-vllm-docker"
    assert body["tags"] == {"env": "prod"}


async def test_update_missing_box_404(client):
    r = await client.put(
        "/api/boxes/nope",
        json={"name": "x", "host": "h", "user": "u"},
    )
    assert r.status_code == 404


async def test_delete_removes_box(client):
    r = await client.post("/api/boxes", json={"name": "x", "host": "h", "user": "u"})
    bid = r.json()["id"]
    assert (await client.delete(f"/api/boxes/{bid}")).status_code == 204
    assert (await client.get(f"/api/boxes/{bid}")).status_code == 404
