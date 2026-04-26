"""Container actions: pause / unpause / restart / inspect / stats / delete."""

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
    box.set_default(stdout="12345\n", exit=0)  # default permissive

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


async def _start_launch(ls, box_svc, lib, *, model="qwen/x"):
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model=model))
    return await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))


async def test_pause_picks_model_match_when_multiple_candidates(env):
    """Image filter alone catches multiple containers; model substring picks."""
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/model-x")
    fake.reply(
        "docker ps --no-trunc --filter ancestor=vllm-node "
        "--filter status=running --format '{{.ID}}|{{.Command}}'",
        stdout=(
            "ABC123|python -m vllm.entrypoints.openai.api_server\n"
            "DEF456|vllm serve org/model-x --tp 2\n"
        ),
    )
    fake.reply("docker pause DEF456", stdout="DEF456\n")
    after = await ls.pause(rec.id)
    assert after.state == LaunchState.paused
    assert after.container_id == "DEF456"


async def test_pause_falls_back_to_first_when_model_not_in_command(env):
    """Real-world case: vLLM runs as `python -m vllm.entrypoints...` and the
    model id doesn't appear literally in the docker Command field. We should
    still pick the (only) running container with the right image."""
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/model-x")
    fake.reply(
        "docker ps --no-trunc --filter ancestor=vllm-node "
        "--filter status=running --format '{{.ID}}|{{.Command}}'",
        stdout="F7B999F2D8A5|python -m vllm.entrypoints.openai.api_server\n",
    )
    fake.reply("docker pause F7B999F2D8A5", stdout="F7B999F2D8A5\n")
    after = await ls.pause(rec.id)
    assert after.container_id == "F7B999F2D8A5"


async def test_resolve_re_discovers_when_cached_id_is_stale(env):
    """The cached container id might be from a build/intermediate container
    that no longer exists. We must verify it's still running and re-discover."""
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/x")
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Launch

    async with session_scope() as s:
        row = await s.get(Launch, rec.id)
        row.container_id = "STALEID"
    # cached id check returns empty → not running anymore
    fake.reply(
        "docker ps -q --filter id=STALEID --filter status=running", stdout=""
    )
    fake.reply(
        "docker ps --no-trunc --filter ancestor=vllm-node "
        "--filter status=running --format '{{.ID}}|{{.Command}}'",
        stdout="LIVEID|python -m vllm\n",
    )
    fake.reply("docker pause LIVEID", stdout="LIVEID\n")
    after = await ls.pause(rec.id)
    assert after.container_id == "LIVEID"


async def test_unpause_returns_to_healthy(env):
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/x")
    # short-circuit container discovery by pre-caching the id
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Launch

    async with session_scope() as s:
        row = await s.get(Launch, rec.id)
        row.container_id = "ZZZ"
    fake.reply("docker unpause ZZZ", stdout="ZZZ\n")
    after = await ls.unpause(rec.id)
    assert after.state == LaunchState.healthy
    assert after.container_id == "ZZZ"


async def test_inspect_returns_parsed_json(env):
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/x")
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Launch

    async with session_scope() as s:
        row = await s.get(Launch, rec.id)
        row.container_id = "ZZZ"
    fake.reply(
        "docker inspect ZZZ",
        stdout='[{"Id":"abc","State":{"Status":"running"}}]\n',
    )
    out = await ls.inspect(rec.id)
    assert out["container_id"] == "ZZZ"
    assert out["inspect"]["State"]["Status"] == "running"


async def test_restart_sets_starting(env):
    ls, box_svc, lib, fake, _ = env
    rec = await _start_launch(ls, box_svc, lib, model="org/x")
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Launch

    async with session_scope() as s:
        row = await s.get(Launch, rec.id)
        row.container_id = "ZZZ"
    fake.reply("docker restart ZZZ", stdout="ZZZ\n")
    after = await ls.restart_container(rec.id)
    assert after.state == LaunchState.starting


async def test_list_active_only_filters_terminal_states(env):
    ls, box_svc, lib, fake, _ = env
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    a = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    b = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    # mark one stopped manually
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Launch

    async with session_scope() as s:
        row = await s.get(Launch, b.id)
        row.state = LaunchState.stopped.value

    all_ = await ls.list()
    active = await ls.list(active_only=True)
    assert {l.id for l in all_} == {a.id, b.id}
    assert {l.id for l in active} == {a.id}


async def test_delete_removes_row(env):
    ls, box_svc, lib, _fake, _ = env
    rec = await _start_launch(ls, box_svc, lib)
    await ls.delete(rec.id)
    listed = await ls.list()
    assert listed == []
