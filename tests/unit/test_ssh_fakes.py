import asyncssh

from tests.ssh_fakes import FakeBox


async def test_fake_box_responds_to_known_command(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: NVIDIA GB10\n")
    async with asyncssh.connect(
        "127.0.0.1",
        port=port,
        username="x",
        password="y",
        known_hosts=None,
        client_keys=None,
    ) as conn:
        result = await conn.run("nvidia-smi -L", check=False)
    assert result.exit_status == 0
    assert "GB10" in result.stdout
    assert "nvidia-smi -L" in box.received
