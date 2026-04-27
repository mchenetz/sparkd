"""Cluster grouping by `cluster` tag + advisor cluster awareness."""

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.advisor import AdvisorChunk
from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCapabilities


class CapturingPort:
    def __init__(self) -> None:
        self.last_cluster: dict | None = None

    async def _yield(self) -> AsyncIterator[AdvisorChunk]:
        text = (
            '```json\n{"name":"x","model":"org/m","args":{},"env":{},'
            '"description":"d","rationale":"r"}\n```'
        )
        for ch in text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=1, output_tokens=1, final=True)

    async def stream_recipe(self, info, caps, history, *, cluster=None):
        self.last_cluster = cluster
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

    async def fake_caps(_self, box_id, *, refresh=False):
        return BoxCapabilities(
            gpu_count=1,
            gpu_model="NVIDIA GB10",
            vram_per_gpu_gb=128,
            ib_interface="mlx5_0",
            captured_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(type(app.state.boxes), "capabilities", fake_caps)

    async def fake_hf(_self, model_id):
        from sparkd.schemas.hf import HFModelInfo

        return HFModelInfo(
            id=model_id, architecture="X", parameters_b=1.0, context_length=4096
        )

    monkeypatch.setattr(type(app.state.hf), "fetch", fake_hf)
    port = CapturingPort()
    app.state.advisor.port = port
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app, port
    await app.state.pool.close_all()


async def _make_box(c, name: str, host: str, *, cluster: str | None = None):
    body = {
        "name": name,
        "host": host,
        "user": "u",
        "tags": {"cluster": cluster} if cluster else {},
    }
    return (await c.post("/api/boxes", json=body)).json()


async def test_clusters_groups_boxes_by_tag(client):
    c, _app, _port = client
    await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    await _make_box(c, "n2", "10.0.0.2", cluster="alpha")
    await _make_box(c, "n3", "10.0.0.3", cluster="alpha")
    await _make_box(c, "loner", "10.0.0.99")  # no cluster tag
    await _make_box(c, "beta-1", "10.0.0.10", cluster="beta")

    r = await c.get("/api/clusters")
    assert r.status_code == 200
    body = r.json()
    by_name = {cl["name"]: cl for cl in body["clusters"]}
    assert by_name["alpha"]["box_count"] == 3
    assert by_name["beta"]["box_count"] == 1
    assert "loner" not in by_name


async def test_get_cluster_returns_member_boxes(client):
    c, _app, _port = client
    a = await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    b = await _make_box(c, "n2", "10.0.0.2", cluster="alpha")
    r = await c.get("/api/clusters/alpha")
    assert r.status_code == 200
    body = r.json()
    ids = {x["id"] for x in body["boxes"]}
    assert ids == {a["id"], b["id"]}


async def test_get_unknown_cluster_404(client):
    c, _app, _port = client
    r = await c.get("/api/clusters/nope")
    assert r.status_code == 404


async def test_advisor_recipe_with_cluster_target_passes_topology(client):
    c, _app, port = client
    await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    await _make_box(c, "n2", "10.0.0.2", cluster="alpha")
    await _make_box(c, "n3", "10.0.0.3", cluster="alpha")
    sid = (
        await c.post(
            "/api/advisor/sessions",
            json={
                "kind": "recipe",
                "target_box_id": "cluster:alpha",
                "hf_model_id": "org/m",
            },
        )
    ).json()["id"]
    r = await c.post(f"/api/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    # The port captured the cluster context
    assert port.last_cluster is not None
    assert port.last_cluster["name"] == "alpha"
    assert len(port.last_cluster["nodes"]) == 3
    assert port.last_cluster["total_gpus"] == 3
    assert port.last_cluster["total_vram_gb"] == 384  # 3 nodes × 1 GPU × 128 GB


async def test_advisor_with_single_box_target_no_cluster_context(client):
    c, _app, port = client
    box = await _make_box(c, "solo", "10.0.0.50")
    sid = (
        await c.post(
            "/api/advisor/sessions",
            json={
                "kind": "recipe",
                "target_box_id": box["id"],
                "hf_model_id": "org/m",
            },
        )
    ).json()["id"]
    r = await c.post(f"/api/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    assert port.last_cluster is None
