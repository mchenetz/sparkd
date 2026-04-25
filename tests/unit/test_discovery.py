import pytest

from sparkd.ssh.discovery import probe_host


async def test_probe_returns_dgx_when_gb10_present(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: NVIDIA GB10 12.1a\n")
    result = await probe_host("127.0.0.1", port=port, user="x", password="y")
    assert result.is_dgx_spark is True
    assert "GB10" in result.gpu_line


async def test_probe_returns_not_dgx_when_no_gb10(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: Tesla V100\n")
    result = await probe_host("127.0.0.1", port=port, user="x", password="y")
    assert result.is_dgx_spark is False


async def test_probe_returns_unreachable_when_port_closed():
    result = await probe_host("127.0.0.1", port=1, user="x", password="y", timeout=0.5)
    assert result.reachable is False
