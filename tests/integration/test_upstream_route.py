import httpx
import pytest
import respx
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


@respx.mock
async def test_sync_upstream_imports_then_appears_in_list(client):
    respx.get(
        "https://api.github.com/repos/eugr/spark-vllm-docker/contents/recipes"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "alpha.yaml",
                    "type": "file",
                    "download_url": "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/alpha.yaml",
                },
            ],
        )
    )
    respx.get(
        "https://raw.githubusercontent.com/eugr/spark-vllm-docker/main/recipes/alpha.yaml"
    ).mock(
        return_value=httpx.Response(
            200, text="name: alpha\nmodel: org/alpha\ndefaults:\n  tensor_parallel: 1\n"
        )
    )
    r = await client.post("/recipes/sync-upstream", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == ["alpha"]
    listing = (await client.get("/recipes")).json()
    assert any(r["name"] == "alpha" for r in listing)


@respx.mock
async def test_sync_upstream_404_returns_502(client):
    respx.get(
        "https://api.github.com/repos/nope/nope/contents/recipes"
    ).mock(return_value=httpx.Response(404, json={}))
    r = await client.post(
        "/recipes/sync-upstream",
        json={"repo": "nope/nope", "branch": "main"},
    )
    assert r.status_code == 502
    assert r.headers["content-type"].startswith("application/problem+json")
