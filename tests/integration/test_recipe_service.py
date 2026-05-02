from datetime import datetime, timezone

import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCapabilities, BoxCreate
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.box import BoxService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def svc(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    pool = SSHPool()
    box_svc = BoxService(pool=pool)
    lib = LibraryService()
    box, port = fake_box
    monkeypatch.setattr(
        box_svc,
        "_target_for",
        lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    yield RecipeService(library=lib, boxes=box_svc, pool=pool), box_svc, box, port
    await pool.close_all()


def _caps(gpu_count: int, vram: int = 96) -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=gpu_count,
        gpu_model="NVIDIA GB10",
        vram_per_gpu_gb=vram,
        captured_at=datetime.now(timezone.utc),
    )


async def test_validate_passes_when_tp_matches_gpu_count(svc, monkeypatch):
    rs, box_svc, _, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))

    async def fake_caps(*_a, **_k):
        return _caps(2)

    monkeypatch.setattr(box_svc, "capabilities", fake_caps)
    r = RecipeSpec(name="r", model="m", args={"--tensor-parallel-size": "2"})
    issues = await rs.validate(r, bs.id)
    assert issues == []


async def test_validate_fails_when_tp_exceeds_gpus(svc, monkeypatch):
    rs, box_svc, _, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))

    async def fake_caps(*_a, **_k):
        return _caps(1)

    monkeypatch.setattr(box_svc, "capabilities", fake_caps)
    r = RecipeSpec(name="r", model="m", args={"--tensor-parallel-size": "4"})
    issues = await rs.validate(r, bs.id)
    assert any("tensor-parallel-size" in i for i in issues)


async def test_sync_writes_yaml_to_box_repo(svc):
    rs, box_svc, fake, _port = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    rs.library.save_recipe(RecipeSpec(name="r1", model="m", args={"--tp": "1"}))
    await rs.sync("r1", bs.id)
    assert any("recipes/r1.yaml" in c for c in fake.received)


async def test_sync_extra_env_merges_into_yaml(svc):
    """extra_env is appended to the recipe's env block (defaults-only merge);
    new keys land, existing keys are not clobbered. Verified by reading the
    heredoc payload that lands on the fake box."""
    rs, box_svc, fake, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    rs.library.save_recipe(
        RecipeSpec(
            name="r1",
            model="m",
            env={"NCCL_SOCKET_IFNAME": "ibp0"},
        )
    )
    await rs.sync(
        "r1",
        bs.id,
        extra_env={
            "VLLM_HOST_IP": "$LOCAL_IP",
            "NCCL_SOCKET_IFNAME": "should-not-overwrite",
        },
    )
    blob = "\n".join(fake.received)
    assert "VLLM_HOST_IP: $LOCAL_IP" in blob
    # Existing key kept its original value — defaults-only merge.
    assert "NCCL_SOCKET_IFNAME: ibp0" in blob
    assert "should-not-overwrite" not in blob


async def test_sync_without_extra_env_passes_yaml_byte_identical(svc):
    """No extra_env → the on-disk YAML is shipped verbatim, preserving
    upstream-format fields like `defaults`/`command`/`container`."""
    rs, box_svc, fake, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    raw = (
        "name: r1\n"
        "model: m\n"
        "container: vllm-node\n"
        "defaults: { port: 8000 }\n"
        "command: vllm serve {model} --port {port}\n"
    )
    rs.library.save_recipe_raw("r1", raw)
    await rs.sync("r1", bs.id)
    blob = "\n".join(fake.received)
    # The literal `command:` template survives — we did not re-serialize.
    assert "vllm serve {model} --port {port}" in blob
