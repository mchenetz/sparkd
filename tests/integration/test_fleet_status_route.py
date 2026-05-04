"""Cluster-aware fleet status endpoint — verifies the snapshot groups
boxes by cluster, surfaces active launches per cluster (driven by
reconciler-maintained Launch.state in the DB), distinguishes head/
worker roles, and only flags drift when something is genuinely
unaccounted-for.

The legacy per-box `/api/boxes/<id>/status` endpoint stays for the
BoxDetail drilldown — these tests only exercise the new
`/api/status/fleet` shape."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine, session_scope
from sparkd.db.models import Launch
from sparkd.services.status import StatusService


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()

    # Stub docker ps — return empty by default; tests can patch per-box.
    async def fake_docker_ps_safe(self, box_id):
        return ("online", [])

    monkeypatch.setattr(
        StatusService, "_docker_ps_safe", fake_docker_ps_safe
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


async def _make_box(c, name, host, *, cluster=None):
    return (
        await c.post(
            "/api/boxes",
            json={
                "name": name,
                "host": host,
                "user": "u",
                "tags": {"cluster": cluster} if cluster else {},
            },
        )
    ).json()


async def _insert_launch(box_id, *, cluster_name=None, container_id=None,
                          state="healthy", recipe="r1"):
    async with session_scope() as s:
        row = Launch(
            id="lid" + box_id[:6],
            box_id=box_id,
            cluster_name=cluster_name,
            recipe_name=recipe,
            recipe_snapshot_json={},
            mods_json=[],
            state=state,
            container_id=container_id,
            command="…",
            log_path=None,
        )
        s.add(row)
        await s.flush()
    return row


async def test_fleet_snapshot_lists_clusters_with_members_and_roles(client):
    c, _app = client
    a = await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    b = await _make_box(c, "n2", "10.0.0.2", cluster="alpha")

    r = await c.get("/api/status/fleet")
    assert r.status_code == 200
    data = r.json()
    assert len(data["clusters"]) == 1
    cl = data["clusters"][0]
    assert cl["name"] == "alpha"
    # Head is the first registered, worker is the second.
    assert cl["members"][0]["box_id"] == a["id"]
    assert cl["members"][0]["role"] == "head"
    assert cl["members"][1]["box_id"] == b["id"]
    assert cl["members"][1]["role"] == "worker"
    # No active launch yet.
    assert cl["active_launch"] is None


async def test_fleet_snapshot_attaches_active_launch_to_cluster(client, monkeypatch):
    """An active cluster launch shows up at the cluster level (not as
    drift on the worker, which was the original symptom). The launch's
    state comes from the reconciler-maintained DB row."""
    c, _app = client
    a = await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    await _make_box(c, "n2", "10.0.0.2", cluster="alpha")

    # docker ps on the head returns the launch's container.
    async def fake_ps(self, box_id):
        if box_id == a["id"]:
            from sparkd.services.status import DockerContainer

            return (
                "online",
                [
                    DockerContainer(
                        id="abc12345xxx",
                        image="vllm-node",
                        labels={},
                        state="running",
                    )
                ],
            )
        # Worker also runs a vllm-node (Ray worker side).
        from sparkd.services.status import DockerContainer

        return (
            "online",
            [
                DockerContainer(
                    id="def67890yyy",
                    image="vllm-node",
                    labels={},
                    state="running",
                )
            ],
        )

    monkeypatch.setattr(StatusService, "_docker_ps_safe", fake_ps)
    await _insert_launch(
        a["id"],
        cluster_name="alpha",
        container_id="abc12345xxx",
        state="healthy",
        recipe="qwen3-122b",
    )

    r = await c.get("/api/status/fleet")
    data = r.json()
    cl = data["clusters"][0]
    assert cl["active_launch"] is not None
    assert cl["active_launch"]["recipe_name"] == "qwen3-122b"
    assert cl["active_launch"]["state"] == "healthy"
    assert cl["active_launch"]["cluster_name"] == "alpha"
    # The head's container_id is pinned on the head member.
    assert cl["members"][0]["container_id"] == "abc12345xxx"
    # The worker's vllm-node container is NOT flagged as drift —
    # it's accepted as the worker side of the cluster launch.
    assert data["drift_external_containers"] == []


async def test_fleet_snapshot_flags_drift_for_truly_external_container(
    client, monkeypatch
):
    """A vllm-node container on a standalone box with no launch claiming
    it IS drift — that's hand-started or leftover."""
    c, _app = client
    box = await _make_box(c, "solo", "10.0.0.99")  # no cluster

    async def fake_ps(self, box_id):
        from sparkd.services.status import DockerContainer

        return (
            "online",
            [
                DockerContainer(
                    id="orphan001xx",
                    image="vllm-node",
                    labels={},
                    state="running",
                )
            ],
        )

    monkeypatch.setattr(StatusService, "_docker_ps_safe", fake_ps)
    r = await c.get("/api/status/fleet")
    data = r.json()
    drift = data["drift_external_containers"]
    assert len(drift) == 1
    assert drift[0]["container_id"] == "orphan001xx"  # 12-char trimmed
    assert drift[0]["image"] == "vllm-node"
    assert drift[0]["box_name"] == "solo"
    _ = box


async def test_fleet_snapshot_flags_orphan_launch_when_container_missing(
    client, monkeypatch
):
    """A launch DB row whose container has vanished is an orphan launch.
    (The reconciler will eventually mark it `interrupted` and demote it
    out of active states; until then the snapshot surfaces it as drift
    so the user sees something is wrong.)"""
    c, _app = client
    box = await _make_box(c, "solo", "10.0.0.99")

    # docker ps returns NO containers.
    await _insert_launch(
        box["id"],
        container_id="ghosted0001",
        state="healthy",
        recipe="r1",
    )

    r = await c.get("/api/status/fleet")
    data = r.json()
    assert "lid" + box["id"][:6] in data["drift_orphan_launches"]


async def test_per_box_snapshot_marks_worker_container_as_cluster_worker(
    client, monkeypatch
):
    """The per-box (BoxDetail) snapshot must also be cluster-aware.
    Without this, BoxDetailPage shows DOWN/EXTERNAL for a healthy
    worker — the bug the user saw at /boxes/<worker_id>."""
    c, _app = client
    head = await _make_box(c, "n1", "10.0.0.1", cluster="alpha")
    worker = await _make_box(c, "n2", "10.0.0.2", cluster="alpha")

    # docker ps on worker returns a vllm-node Ray-worker container.
    async def fake_ps(self, box_id):
        from sparkd.services.status import DockerContainer

        if box_id == worker["id"]:
            return (
                "online",
                [
                    DockerContainer(
                        id="workercid01",
                        image="vllm-node",
                        labels={},
                        state="running",
                    )
                ],
            )
        return ("online", [])

    monkeypatch.setattr(StatusService, "_docker_ps_safe", fake_ps)

    # Stub the per-box _docker_ps as well (snapshot() uses this directly)
    async def fake_docker_ps(self, box_id):
        ok, c_list = await fake_ps(self, box_id)
        return c_list

    monkeypatch.setattr(StatusService, "_docker_ps", fake_docker_ps)

    # /health probe always returns healthy — verifies that the worker
    # snapshot probes the head (which is up), not its own port.
    probe_calls = []

    async def fake_probe(self, host, port=8000):
        probe_calls.append(host)
        return ["org/m"], True

    monkeypatch.setattr(StatusService, "_vllm_probe", fake_probe)

    # Active cluster launch on the head.
    await _insert_launch(
        head["id"],
        cluster_name="alpha",
        container_id="headcid001",
        state="healthy",
        recipe="qwen3-cluster",
    )

    # Hit the per-box endpoint for the WORKER.
    r = await c.get(f"/api/boxes/{worker['id']}/status")
    assert r.status_code == 200
    data = r.json()
    rm = data["running_models"]
    assert len(rm) == 1
    assert rm[0]["source"] == "cluster-worker"
    assert rm[0]["recipe_name"] == "qwen3-cluster"
    assert rm[0]["healthy"] is True
    # And confirm we probed the HEAD's host, not the worker's.
    assert "10.0.0.1" in probe_calls
    assert "10.0.0.2" not in probe_calls


async def test_fleet_snapshot_marks_offline_box_connectivity(client, monkeypatch):
    c, _app = client
    await _make_box(c, "solo", "10.0.0.99")

    async def fake_ps(self, box_id):
        return ("offline", [])

    monkeypatch.setattr(StatusService, "_docker_ps_safe", fake_ps)
    r = await c.get("/api/status/fleet")
    data = r.json()
    assert data["standalones"][0]["member"]["connectivity"] == "offline"
