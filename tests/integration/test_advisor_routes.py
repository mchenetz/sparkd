from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.advisor import AdvisorChunk
from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCapabilities


class FakePort:
    def __init__(self, text: str) -> None:
        self.text = text

    async def _yield(self) -> AsyncIterator[AdvisorChunk]:
        for ch in self.text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=4, output_tokens=8, final=True)

    async def stream_recipe(self, info, caps, history, *, cluster=None):
        async for c in self._yield():
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield():
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield():
            yield c


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()
    text = (
        '```json\n{"name":"r1","model":"x/y",'
        '"args":{"--tp":"1"},"env":{},"description":"d","rationale":"r"}\n```'
    )
    app.state.advisor.port = FakePort(text)

    async def fake_caps(_self, _box_id, *, refresh=False):
        return BoxCapabilities(
            gpu_count=1,
            gpu_model="GB10",
            vram_per_gpu_gb=96,
            captured_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(type(app.state.boxes), "capabilities", fake_caps)

    async def fake_hf(_self, model_id):
        from sparkd.schemas.hf import HFModelInfo

        return HFModelInfo(
            id=model_id, architecture="X", parameters_b=1.0, context_length=4096
        )

    monkeypatch.setattr(type(app.state.hf), "fetch", fake_hf)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


async def test_create_session_then_generate_recipe(client):
    c, _app = client
    bid = (
        await c.post("/api/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    r = await c.post(
        "/api/advisor/sessions",
        json={"kind": "recipe", "target_box_id": bid, "hf_model_id": "x/y"},
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await c.post(f"/api/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["draft"]["name"] == "r1"
    r = await c.get(f"/api/advisor/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["input_tokens"] == 4
    assert r.json()["output_tokens"] == 8
