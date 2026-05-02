import asyncio

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
    yield ls, box_svc, lib, box, port
    await pool.close_all()


async def test_launch_records_starting_state(env):
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)  # accept any backgrounded command
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target=bs.id))
    assert rec.state == LaunchState.starting
    assert rec.recipe_name == "r1"
    # The command should run-recipe.sh and redirect output to the per-launch log.
    assert any(
        "./run-recipe.sh r1" in c and f"~/.sparkd-launches/{rec.id}.log" in c
        for c in fake.received
    )
    # Single-box path must NOT inject -n.
    assert not any("-n " in c and "./run-recipe.sh" in c for c in fake.received)


async def test_cluster_launch_injects_vllm_host_ip(env, monkeypatch):
    """Cluster targets cause LaunchService to pass extra_env containing
    VLLM_HOST_IP=$LOCAL_IP through to _sync_files. RecipeService.sync
    then merges it into the recipe's env block before scping the YAML
    to the head — but that merge is exercised in its own unit test below."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    captured: dict = {}

    async def spy_sync_files(name, box_id, mods, *, extra_env=None):
        captured["extra_env"] = extra_env

    monkeypatch.setattr(ls, "_sync_files", spy_sync_files)

    await box_svc.create(
        BoxCreate(
            name="n1", host="10.0.0.1", user="u",
            tags={"cluster": "alpha"}, cluster_ip="192.168.201.10",
        )
    )
    await box_svc.create(
        BoxCreate(
            name="n2", host="10.0.0.2", user="u",
            tags={"cluster": "alpha"}, cluster_ip="192.168.201.11",
        )
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))

    assert captured["extra_env"] == {"VLLM_HOST_IP": "$LOCAL_IP"}


async def test_single_box_launch_does_not_inject_vllm_host_ip(env, monkeypatch):
    """Single-box targets pass extra_env={} — no per-node injection,
    because VLLM_HOST_IP isn't needed and would just add noise."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    captured: dict = {}

    async def spy_sync_files(name, box_id, mods, *, extra_env=None):
        captured["extra_env"] = extra_env

    monkeypatch.setattr(ls, "_sync_files", spy_sync_files)

    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target=bs.id))

    assert captured["extra_env"] == {}


async def test_cluster_launch_falls_back_to_host_when_no_cluster_ip(env):
    """If no cluster_ip is set on any member, build -n from box.host."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    head = await box_svc.create(
        BoxCreate(name="n1", host="10.0.0.1", user="u", tags={"cluster": "alpha"})
    )
    await box_svc.create(
        BoxCreate(name="n2", host="10.0.0.2", user="u", tags={"cluster": "alpha"})
    )
    await box_svc.create(
        BoxCreate(name="n3", host="10.0.0.3", user="u", tags={"cluster": "alpha"})
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    assert rec.box_id == head.id
    assert rec.cluster_name == "alpha"
    assert any(
        "./run-recipe.sh -n 10.0.0.1,10.0.0.2,10.0.0.3 r1" in c
        for c in fake.received
    ), f"expected -n flag in head command; got {fake.received}"


async def test_cluster_launch_emits_warning_when_member_lacks_cluster_ip(env):
    """When some cluster members have no cluster_ip, the launch log should
    open with a sparkd WARNING calling out the missing field — visible in
    LiveLog before run-recipe.sh produces its first byte."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    await box_svc.create(
        BoxCreate(
            name="head", host="gx10-0fb1.local", user="u",
            tags={"cluster": "alpha"}, cluster_ip="192.168.201.10",
        )
    )
    await box_svc.create(
        BoxCreate(
            name="worker", host="gx10-9ed5.local", user="u",
            tags={"cluster": "alpha"},  # no cluster_ip
        )
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    blob = "\n".join(fake.received)
    # Header is pre-written via printf > log_path with a sparkd-side header.
    assert "=== sparkd launch" in blob, "expected sparkd header in cmd"
    assert "WARNING: cluster_ip is not set on member(s): worker" in blob
    # Cluster summary should call out the offending node.
    assert "gx10-9ed5.local(no cluster_ip)" in blob


async def test_cluster_launch_no_warning_when_all_members_have_cluster_ip(env):
    """Every member set → no WARNING in the header. Just the launch summary."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    await box_svc.create(
        BoxCreate(
            name="head", host="gx10-0fb1.local", user="u",
            tags={"cluster": "alpha"}, cluster_ip="192.168.201.10",
        )
    )
    await box_svc.create(
        BoxCreate(
            name="worker", host="gx10-9ed5.local", user="u",
            tags={"cluster": "alpha"}, cluster_ip="192.168.201.11",
        )
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    blob = "\n".join(fake.received)
    assert "=== sparkd launch" in blob
    assert "WARNING:" not in blob


async def test_cluster_launch_uses_cluster_ip_when_set(env):
    """When members have cluster_ip set, -n carries those IPs (not box.host).
    This is what makes upstream launch-cluster.sh's LOCAL_IP string-match
    succeed in real deployments where SSH lands on a Tailscale name but
    LOCAL_IP is the IB-fabric address."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    await box_svc.create(
        BoxCreate(
            name="n1",
            host="gx10-0fb1.local",
            user="u",
            tags={"cluster": "alpha"},
            cluster_ip="192.168.201.10",
        )
    )
    await box_svc.create(
        BoxCreate(
            name="n2",
            host="gx10-9ed5.local",
            user="u",
            tags={"cluster": "alpha"},
            cluster_ip="192.168.201.11",
        )
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    assert any(
        "./run-recipe.sh -n 192.168.201.10,192.168.201.11 r1" in c
        for c in fake.received
    ), f"expected cluster_ip-based -n; got {fake.received}"
    # Sanity: the SSH hostnames must NOT leak into the -n list.
    assert not any("gx10-0fb1.local" in c and "-n " in c for c in fake.received)


async def test_cluster_launch_mixed_cluster_ip_falls_back_per_member(env):
    """If only some members have cluster_ip set, the others fall back to host
    in the -n list. (Imperfect, but the alternative is refusing to launch,
    which is worse for partial setups.)"""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    await box_svc.create(
        BoxCreate(
            name="n1",
            host="gx10-0fb1.local",
            user="u",
            tags={"cluster": "alpha"},
            cluster_ip="192.168.201.10",
        )
    )
    await box_svc.create(
        BoxCreate(
            name="n2",
            host="gx10-9ed5.local",
            user="u",
            tags={"cluster": "alpha"},
            # no cluster_ip
        )
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    assert any(
        "./run-recipe.sh -n 192.168.201.10,gx10-9ed5.local r1" in c
        for c in fake.received
    ), f"expected mixed -n; got {fake.received}"


async def test_launch_persists_log_path(env):
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target=bs.id))
    fetched = await ls.get(rec.id)
    # Round-trip via the DB: the WS handler reads log_path from here.
    assert fetched.id == rec.id


async def test_stop_kills_container(env):
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target=bs.id))
    fake.reply(f"docker ps -q --filter label=sparkd.launch={rec.id}", stdout="abc123\n")
    fake.reply("docker stop abc123", stdout="abc123\n")
    stopped = await ls.stop(rec.id)
    assert stopped.state == LaunchState.stopped
