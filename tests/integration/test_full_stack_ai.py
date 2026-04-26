"""End-to-end coverage of HF + advisor + mods using a fake AdvisorPort."""

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from sparkd.advisor import AdvisorChunk
from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCapabilities


class FakePort:
    def __init__(self, recipe_text: str, mod_text: str) -> None:
        self.recipe_text = recipe_text
        self.mod_text = mod_text

    async def _yield(self, text: str) -> AsyncIterator[AdvisorChunk]:
        for ch in text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=10, output_tokens=20, final=True)

    async def stream_recipe(self, info, caps, history):
        async for c in self._yield(self.recipe_text):
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield(self.recipe_text):
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield(self.mod_text):
            yield c


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()
    recipe_text = (
        '```json\n{"name":"llama-8b","model":"meta-llama/Llama-3.1-8B-Instruct",'
        '"args":{"--tensor-parallel-size":"2"},"env":{},'
        '"description":"d","rationale":"r"}\n```'
    )
    mod_text = (
        '```json\n{"name":"fix-vocab","target_models":["llama"],'
        '"files":{"patch.diff":"--- a\\n+++ b\\n"},'
        '"description":"d","rationale":"r"}\n```'
    )
    app.state.advisor.port = FakePort(recipe_text, mod_text)

    async def fake_caps(_self, _box_id, *, refresh=False):
        return BoxCapabilities(
            gpu_count=2,
            gpu_model="NVIDIA GB10",
            vram_per_gpu_gb=96,
            captured_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(type(app.state.boxes), "capabilities", fake_caps)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


@respx.mock
async def test_full_recipe_flow(client):
    c, _app = client
    respx.get(
        "https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "meta-llama/Llama-3.1-8B-Instruct",
                "config": {
                    "architectures": ["LlamaForCausalLM"],
                    "max_position_embeddings": 131072,
                },
                "safetensors": {"total": 16_000_000_000},
            },
        )
    )
    box_id = (
        await c.post("/api/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    sid = (
        await c.post(
            "/api/advisor/sessions",
            json={
                "kind": "recipe",
                "target_box_id": box_id,
                "hf_model_id": "meta-llama/Llama-3.1-8B-Instruct",
            },
        )
    ).json()["id"]
    r = await c.post(f"/api/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft["name"] == "llama-8b"
    r = await c.post(
        "/api/recipes",
        json={
            "name": draft["name"],
            "model": draft["model"],
            "args": draft["args"],
            "env": draft["env"],
            "mods": [],
        },
    )
    assert r.status_code == 201
    r = await c.get(f"/api/advisor/sessions/{sid}")
    assert r.json()["input_tokens"] == 10
    assert r.json()["output_tokens"] == 20


async def test_full_mod_flow(client):
    c, _app = client
    sid = (
        await c.post(
            "/api/advisor/sessions",
            json={"kind": "mod", "hf_model_id": "meta-llama/x"},
        )
    ).json()["id"]
    r = await c.post(
        f"/api/advisor/sessions/{sid}/mod",
        json={"error_log": "ImportError: foo"},
    )
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft["name"] == "fix-vocab"
    r = await c.post(
        "/api/mods",
        json={
            "name": draft["name"],
            "target_models": draft["target_models"],
            "description": draft["description"],
            "files": draft["files"],
            "enabled": True,
        },
    )
    assert r.status_code == 201
    r = await c.get("/api/mods")
    assert any(m["name"] == "fix-vocab" for m in r.json())
