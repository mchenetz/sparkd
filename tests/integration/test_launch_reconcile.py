"""Background reconciler: drives Launch.state from `starting` to `healthy`
once vLLM responds; back-pressures to `starting` when /health stops 200ing;
marks `interrupted` when the container is gone for a healthy launch.

The reconciler is what makes launches survive UI disconnects and sparkd
restarts at the *state-tracking* level — the vLLM process itself runs
under nohup on the box, but the DB row's `state` only progresses because
this loop polls and writes back."""

import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCreate
from sparkd.schemas.launch import LaunchCreate, LaunchState
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.box import BoxService
from sparkd.services.launch import LaunchService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def env(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    pool = SSHPool()
    box_svc = BoxService(pool=pool)
    lib = LibraryService()
    rs = RecipeService(library=lib, boxes=box_svc, pool=pool)
    ls = LaunchService(library=lib, boxes=box_svc, recipes=rs, pool=pool)
    box, port = fake_box
    box.set_default(stdout="12345\n", exit=0)
    monkeypatch.setattr(
        box_svc,
        "_target_for",
        lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )

    async def fake_validate(_spec, _box_id):
        return []

    monkeypatch.setattr(rs, "validate", fake_validate)

    async def fake_sync(*_a, **_k):
        return None

    monkeypatch.setattr(ls, "_sync_files", fake_sync)
    yield ls, box_svc, lib, box, port, monkeypatch
    await pool.close_all()


async def _start_launch(ls, box_svc, lib):
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="qwen/x"))
    return await ls.launch(LaunchCreate(recipe="r1", target=bs.id))


async def test_reconcile_starting_to_healthy_when_vllm_responds(env):
    """Launch sits at `starting`; reconcile probes vLLM, gets 200,
    flips to `healthy`."""
    ls, box_svc, lib, fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)
    assert rec.state == LaunchState.starting

    # Container exists in `docker ps` (resolve_container path).
    fake.reply("docker ps --no-trunc --filter ancestor", stdout="abc12345|cmd\n")
    fake.reply("docker ps -a -q --filter id=", stdout="abc12345\n")

    # Probe says healthy.
    async def fake_probe(_self, host, port=8000):
        return True

    monkeypatch.setattr(LaunchService, "_probe_vllm", fake_probe)

    await ls.reconcile_active()
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.healthy


async def test_reconcile_healthy_back_to_starting_when_vllm_unresponsive(env):
    """Launch was healthy; vLLM /health stops 200ing but the container
    is still up. Reconcile drops back to `starting` (recovering)."""
    ls, box_svc, lib, fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)

    # Manually transition the record to `healthy` first.
    await ls._set_state(rec.id, LaunchState.healthy, container_id="abc12345")

    fake.reply("docker ps --no-trunc --filter ancestor", stdout="abc12345|cmd\n")
    fake.reply("docker ps -a -q --filter id=", stdout="abc12345\n")

    async def fake_probe(_self, host, port=8000):
        return False

    monkeypatch.setattr(LaunchService, "_probe_vllm", fake_probe)

    await ls.reconcile_active()
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.starting


async def test_reconcile_marks_interrupted_when_healthy_container_disappears(env):
    """A healthy launch whose container has vanished (--rm cleanup after
    vLLM crash, or external `docker rm`) → state = interrupted.

    Stubbing _resolve_container directly because the fake-SSH server
    matches commands by exact string and the docker invocations encode
    the cached container id and ancestor image — easier to mock the
    higher layer."""
    ls, box_svc, lib, _fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)
    await ls._set_state(rec.id, LaunchState.healthy, container_id="abc12345")

    async def fake_resolve(_self, _launch_id):
        return None, None, None  # cid=None — container is gone

    monkeypatch.setattr(LaunchService, "_resolve_container", fake_resolve)

    await ls.reconcile_active()
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.interrupted
    assert fetched.stopped_at is not None


async def test_reconcile_keeps_starting_when_container_not_yet_up(env):
    """Initial state: launch dispatched but container hasn't materialized
    yet (slow first-time image pull, weight download, etc.). Don't mark
    interrupted — stay at `starting` so the next tick re-checks."""
    ls, box_svc, lib, _fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)
    assert rec.state == LaunchState.starting

    async def fake_resolve(_self, _launch_id):
        return None, None, None

    monkeypatch.setattr(LaunchService, "_resolve_container", fake_resolve)

    await ls.reconcile_active()
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.starting


async def test_reconcile_skips_terminal_states(env):
    """Stopped / failed / interrupted launches must not be re-probed —
    they're terminal and the user expects them to stay where they are."""
    ls, box_svc, lib, fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)
    await ls._set_state(rec.id, LaunchState.stopped, stopped=True)

    probe_calls = {"n": 0}

    async def counting_probe(_self, host, port=8000):
        probe_calls["n"] += 1
        return True

    monkeypatch.setattr(LaunchService, "_probe_vllm", counting_probe)
    await ls.reconcile_active()
    assert probe_calls["n"] == 0
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.stopped


async def test_reconcile_captures_exit_info_when_marking_interrupted(env):
    """When the reconciler transitions a healthy launch to interrupted
    (container vanished), it should snapshot the tail of the launch log
    and store it on `LaunchRecord.exit_info` so the UI can show the user
    why it died — without forcing them to ssh in and tail logs by hand."""
    ls, box_svc, lib, _fake, _port, monkeypatch = env
    rec = await _start_launch(ls, box_svc, lib)
    await ls._set_state(rec.id, LaunchState.healthy, container_id="abc12345")

    # Container is gone.
    async def fake_resolve(_self, _launch_id):
        return None, None, None

    monkeypatch.setattr(LaunchService, "_resolve_container", fake_resolve)

    # And the launch log on the box ends with a real-looking traceback.
    captured_log_tail = [
        "(APIServer pid=550) Traceback (most recent call last):",
        "(APIServer pid=550)   File \"vllm/serve.py\", line 100, in main",
        "(APIServer pid=550) OSError: Can't load image processor for "
        "'org/some-model'. ...preprocessor_config.json...",
        "Stopping cluster...",
        "Cluster stopped.",
    ]

    async def fake_capture(_self, _launch_id, _target):
        return {
            "tail": captured_log_tail,
            "reason": (
                "OSError: Can't load image processor for 'org/some-model'."
                " ...preprocessor_config.json..."
            ),
            "captured_at": "2026-05-02T20:00:00+00:00",
        }

    monkeypatch.setattr(LaunchService, "_capture_exit_info", fake_capture)

    await ls.reconcile_active()
    fetched = await ls.get(rec.id)
    assert fetched.state == LaunchState.interrupted
    assert fetched.exit_info is not None
    assert fetched.exit_info["reason"].startswith("OSError")
    assert len(fetched.exit_info["tail"]) == 5


async def test_reconcile_swallows_per_launch_errors(env):
    """One launch's reconcile failing must not abort the others — the
    background loop runs under all-or-nothing semantics from the user's
    perspective and shouldn't be derailed by a single offline box."""
    ls, box_svc, lib, fake, _port, monkeypatch = env
    rec1 = await _start_launch(ls, box_svc, lib)

    async def boom(*_a, **_k):
        raise RuntimeError("box went away")

    monkeypatch.setattr(LaunchService, "_reconcile_one", boom)
    # Should not raise.
    await ls.reconcile_active()
    fetched = await ls.get(rec1.id)
    assert fetched.state == LaunchState.starting  # unchanged
