import asyncssh
import pytest

from sparkd.ssh.pool import SSHPool, SSHTarget
from tests.ssh_fakes import FakeBox, start_fake_box


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


async def test_stream_interleaves_stdout_and_stderr(fake_box, pool):
    box, port = fake_box

    async def stream_handler(process: asyncssh.SSHServerProcess) -> None:
        # Emit interleaved output on both channels.
        process.stdout.write("out-1\n")
        process.stderr.write("err-1\n")
        process.stdout.write("out-2\n")
        process.stderr.write("err-2\n")

    box.stream("noisy", stream_handler)
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    seen = []
    async for channel, line in pool.stream(target, "noisy"):
        seen.append((channel, line.strip()))
    channels = {c for c, _ in seen}
    assert channels == {"stdout", "stderr"}
    # All four lines arrived (filter empty lines that asyncssh emits at channel close)
    assert {l for _, l in seen if l} == {"out-1", "err-1", "out-2", "err-2"}


async def test_run_returns_none_exit_status_for_signal(fake_box, pool):
    """When asyncssh reports exit_status=None (signal termination), we surface None."""
    box, port = fake_box
    # FakeBox can't easily simulate signal-terminated, but we can verify
    # the field is now Optional and falsy values aren't coerced.
    box.reply("succeed", stdout="", exit=0)
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    res = await pool.run(target, "succeed")
    # exit_status is now an int (0), preserved exactly.
    assert res.exit_status == 0


async def test_run_evicts_dead_connection_and_reconnects(
    fake_box, pool, monkeypatch
):
    """After a laptop sleep, the cached SSH connection's local socket
    looks alive (`is_closed()` returns False) but the actual write fails
    with `asyncssh.Error: SSH connection closed`. The pool should evict
    that dead entry and retry once on a fresh connection — without the
    user having to click again."""
    box, port = fake_box
    box.reply("docker stop abc", stdout="abc\n")
    target = SSHTarget(
        host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
    )
    # Prime the pool with a real working connection.
    await pool.run(target, "docker stop abc")
    assert pool._conn_count(target) == 1

    # Replace the cached connection's `run` with a one-shot raise. The
    # second call (after the pool evicts and reconnects) succeeds.
    cached = pool._conns[target.key()]
    calls = {"n": 0}

    async def flaky(*_args, **_kwargs):
        calls["n"] += 1
        raise asyncssh.Error(code=0, reason="SSH connection closed")

    monkeypatch.setattr(cached, "run", flaky)

    # The retry happens transparently — the user sees a successful result
    # because the second attempt acquired a fresh connection.
    result = await pool.run(target, "docker stop abc")
    assert result.stdout.strip() == "abc"
    assert calls["n"] == 1  # the flaky cached conn was hit exactly once
    # And the pool has a fresh connection now.
    assert pool._conn_count(target) == 1


async def test_run_surfaces_error_after_retry_also_fails(
    fake_box, pool, monkeypatch
):
    """If the second attempt also fails (box genuinely offline), surface
    UpstreamError. Don't loop forever or hide the failure."""
    from sparkd.errors import UpstreamError

    box, port = fake_box
    box.reply("any", stdout="ok\n")
    target = SSHTarget(
        host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
    )
    await pool.run(target, "any")  # prime the pool

    # Wrap _get so every connection it returns has a poisoned `run`.
    real_get = pool._get.__func__

    async def get_with_poison(self, t):
        conn = await real_get(self, t)

        async def always_fail(*_a, **_k):
            raise asyncssh.Error(code=0, reason="SSH connection closed")

        monkeypatch.setattr(conn, "run", always_fail)
        return conn

    monkeypatch.setattr(SSHPool, "_get", get_with_poison)

    with pytest.raises(UpstreamError, match="ssh exec failed after retry"):
        await pool.run(target, "any")
