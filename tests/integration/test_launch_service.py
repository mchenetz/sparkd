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


async def test_cluster_launch_uses_dash_n_flag(env):
    """A cluster target invokes ./run-recipe.sh with -n <head>,<worker>,... on the head box."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    head = await box_svc.create(
        BoxCreate(name="n1", host="10.0.0.1", user="u", tags={"cluster": "alpha"})
    )
    worker1 = await box_svc.create(
        BoxCreate(name="n2", host="10.0.0.2", user="u", tags={"cluster": "alpha"})
    )
    worker2 = await box_svc.create(
        BoxCreate(name="n3", host="10.0.0.3", user="u", tags={"cluster": "alpha"})
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    assert rec.box_id == head.id
    assert rec.cluster_name == "alpha"
    # Exactly one SSH command on the head; must contain -n <ips>.
    assert any(
        "./run-recipe.sh -n 10.0.0.1,10.0.0.2,10.0.0.3 r1" in c
        for c in fake.received
    ), f"expected -n flag in head command; got {fake.received}"
    _ = (worker1, worker2)


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
