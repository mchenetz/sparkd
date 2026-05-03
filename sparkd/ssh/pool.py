from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import asyncssh

from sparkd.errors import UpstreamError


@dataclass(frozen=True)
class SSHTarget:
    host: str
    port: int
    user: str
    use_agent: bool = True
    ssh_key_path: str | None = None
    password: str | None = None  # tests only

    def key(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int | None  # None means process was terminated by a signal


class SSHPool:
    """Pool of persistent SSH connections, one per (user@host:port) target.

    Self-healing across laptop-sleep / network-flap:

    1. Connections request asyncssh keepalive pings (every 30s, drop after 3
       missed). When the remote drops because we slept, the keepalive
       failure marks the connection closed BEFORE the next user action,
       so `_get()` reconnects transparently rather than handing back a
       dead socket.

    2. `run()` and `stream()` retry once on `OSError`/`asyncssh.Error` —
       even if a stale connection slips past the keepalive check, the
       first command's failure evicts that pool entry and the retry
       happens on a fresh connection. The user sees a tiny stall (one
       reconnect) instead of an "SSH connection closed" error.

    The retry is safe in practice for sparkd's command set: docker
    stop / inspect / ps / `cat .env` are idempotent or read-only.
    """

    # Keep the local view of the connection in sync with reality.
    # Tuned for "wake from laptop sleep should self-heal in <2 min".
    _KEEPALIVE_INTERVAL = 30  # seconds
    _KEEPALIVE_COUNT_MAX = 3  # 3 misses ≈ 90s detection

    def __init__(self) -> None:
        self._conns: dict[str, asyncssh.SSHClientConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _conn_count(self, target: SSHTarget) -> int:
        return 1 if target.key() in self._conns else 0

    def _evict(self, target: SSHTarget) -> None:
        """Drop a (presumed-dead) connection from the pool. Called from the
        retry path after a command fails. Best-effort close — we don't
        await wait_closed because the connection's already half-broken
        and we don't want to block the retry."""
        key = target.key()
        conn = self._conns.pop(key, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    async def _get(self, target: SSHTarget) -> asyncssh.SSHClientConnection:
        key = target.key()
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            existing = self._conns.get(key)
            if existing is not None and not existing.is_closed():
                return existing
            # Drop a closed/half-dead one before reconnecting.
            if existing is not None:
                self._conns.pop(key, None)
            kwargs: dict[str, Any] = {
                "host": target.host,
                "port": target.port,
                "username": target.user,
                "known_hosts": None,
                "keepalive_interval": self._KEEPALIVE_INTERVAL,
                "keepalive_count_max": self._KEEPALIVE_COUNT_MAX,
            }
            if target.password is not None:
                kwargs["password"] = target.password
                kwargs["client_keys"] = None
            elif target.ssh_key_path:
                kwargs["client_keys"] = [target.ssh_key_path]
            elif target.use_agent:
                pass  # asyncssh defaults to agent
            try:
                conn = await asyncssh.connect(**kwargs)
            except (OSError, asyncssh.Error) as exc:
                raise UpstreamError(f"ssh connect failed: {exc}") from exc
            try:
                self._conns[key] = conn
            except BaseException:
                conn.close()
                raise
            return conn

    async def run(self, target: SSHTarget, command: str) -> CommandResult:
        # One automatic retry to absorb stale-connection failures after
        # laptop sleep / network flap. First failure evicts and reconnects;
        # second failure surfaces as UpstreamError.
        last_exc: Exception | None = None
        for attempt in range(2):
            conn = await self._get(target)
            try:
                result = await conn.run(command, check=False)
                return CommandResult(
                    stdout=str(result.stdout or ""),
                    stderr=str(result.stderr or ""),
                    exit_status=result.exit_status,
                )
            except (OSError, asyncssh.Error) as exc:
                last_exc = exc
                self._evict(target)
        raise UpstreamError(
            f"ssh exec failed after retry: {last_exc}"
        ) from last_exc

    async def stream(self, target: SSHTarget, command: str):
        """Yield (channel, line) tuples interleaved from stdout and stderr until the process exits.

        Both streams are drained concurrently to avoid deadlock when the remote
        process produces output on both channels and one fills its window.

        Same retry-once-on-stale-connection logic as `run()` — applied to
        the create_process setup. Once the process is established and we
        start yielding, mid-stream errors surface to the caller (we can't
        retry without losing already-yielded lines).
        """
        proc = None
        last_exc: Exception | None = None
        for attempt in range(2):
            conn = await self._get(target)
            try:
                proc = await conn.create_process(command)
                break
            except (OSError, asyncssh.Error) as exc:
                last_exc = exc
                self._evict(target)
        if proc is None:
            raise UpstreamError(
                f"ssh exec failed after retry: {last_exc}"
            ) from last_exc

        queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

        async def _drain(reader: Any, channel: str) -> None:
            try:
                async for line in reader:
                    await queue.put((channel, line))
            finally:
                await queue.put(None)  # EOF sentinel

        tasks = [
            asyncio.create_task(_drain(proc.stdout, "stdout")),
            asyncio.create_task(_drain(proc.stderr, "stderr")),
        ]
        try:
            done = 0
            while done < 2:
                item = await queue.get()
                if item is None:
                    done += 1
                else:
                    yield item
            await proc.wait()
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            for t in tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

    async def close(self, target: SSHTarget) -> None:
        key = target.key()
        conn = self._conns.pop(key, None)
        self._locks.pop(key, None)
        if conn is not None:
            conn.close()
            await conn.wait_closed()

    async def close_all(self) -> None:
        conns = list(self._conns.values())
        self._conns.clear()
        self._locks.clear()
        for conn in conns:
            conn.close()
        for conn in conns:
            await conn.wait_closed()
