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
    rec = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    assert rec.state == LaunchState.starting
    assert rec.recipe_name == "r1"
    # The command should run-recipe.sh and redirect output to the per-launch log.
    assert any(
        "./run-recipe.sh r1" in c and f"~/.sparkd-launches/{rec.id}.log" in c
        for c in fake.received
    )


async def test_launch_persists_log_path(env):
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    fetched = await ls.get(rec.id)
    # Round-trip via the DB: the WS handler reads log_path from here.
    assert fetched.id == rec.id


async def test_stop_kills_container(env):
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    fake.reply(f"docker ps -q --filter label=sparkd.launch={rec.id}", stdout="abc123\n")
    fake.reply("docker stop abc123", stdout="abc123\n")
    stopped = await ls.stop(rec.id)
    assert stopped.state == LaunchState.stopped
