import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        "sparkd.secrets._backend_set",
        lambda svc, k, v: store.__setitem__((svc, k), v),
    )
    monkeypatch.setattr(
        "sparkd.secrets._backend_get", lambda svc, k: store.get((svc, k))
    )
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store
    await app.state.pool.close_all()


async def test_setup_persists_key_and_status_reports_configured(client):
    c, store = client
    r = await c.post("/api/advisor/setup", json={"anthropic_api_key": "sk-test"})
    assert r.status_code == 200
    assert store[("sparkd", "anthropic_api_key")] == "sk-test"
    r = await c.get("/api/advisor/status")
    assert r.json()["configured"] is True
