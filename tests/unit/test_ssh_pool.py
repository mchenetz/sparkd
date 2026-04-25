import pytest

from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def pool():
    p = SSHPool()
    yield p
    await p.close_all()


async def test_run_returns_stdout(fake_box, pool):
    box, port = fake_box
    box.reply("echo hi", stdout="hi\n")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    result = await pool.run(target, "echo hi")
    assert result.stdout.strip() == "hi"
    assert result.exit_status == 0


async def test_reuses_connection(fake_box, pool):
    box, port = fake_box
    box.reply("a", stdout="A")
    box.reply("b", stdout="B")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    await pool.run(target, "a")
    await pool.run(target, "b")
    # Two commands but should have used one connection.
    assert pool._conn_count(target) == 1


async def test_reconnects_after_close(fake_box, pool):
    box, port = fake_box
    box.reply("a", stdout="A")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    await pool.run(target, "a")
    await pool.close(target)
    await pool.run(target, "a")
    assert pool._conn_count(target) == 1
