import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCreate
from sparkd.services.box import BoxService
from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def svc(sparkd_home):
    await init_engine(create_all=True)
    pool = SSHPool()
    yield BoxService(pool=pool)
    await pool.close_all()


async def test_create_then_get(svc):
    spec = await svc.create(BoxCreate(name="spark-01", host="10.0.0.5", user="ubuntu"))
    assert spec.id
    fetched = await svc.get(spec.id)
    assert fetched.name == "spark-01"


async def test_list_returns_all(svc):
    await svc.create(BoxCreate(name="a", host="h1", user="u"))
    await svc.create(BoxCreate(name="b", host="h2", user="u"))
    rows = await svc.list()
    assert {b.name for b in rows} == {"a", "b"}


async def test_capabilities_parses_nvidia_smi(svc, fake_box, monkeypatch):
    box, port = fake_box
    box.reply(
        "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits",
        stdout="NVIDIA GB10, 96000, 555.42\nNVIDIA GB10, 96000, 555.42\n",
    )
    box.reply("nvcc --version 2>/dev/null || true", stdout="release 12.5\n")
    box.reply(
        "ls /sys/class/infiniband 2>/dev/null || true", stdout="mlx5_0\n"
    )
    spec = await svc.create(
        BoxCreate(name="x", host="127.0.0.1", port=port, user="x")
    )
    monkeypatch.setattr(
        svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    caps = await svc.capabilities(spec.id, refresh=True)
    assert caps.gpu_count == 2
    assert caps.gpu_model == "NVIDIA GB10"
    assert caps.vram_per_gpu_gb == 96
    assert caps.ib_interface == "mlx5_0"


async def test_test_connection_returns_true_when_ssh_ok(svc, fake_box, monkeypatch):
    box, port = fake_box
    box.reply("true", stdout="")
    spec = await svc.create(BoxCreate(name="x", host="127.0.0.1", port=port, user="x"))
    monkeypatch.setattr(
        svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    assert await svc.test_connection(spec.id) is True
