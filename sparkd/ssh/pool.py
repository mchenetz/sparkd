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
    def __init__(self) -> None:
        self._conns: dict[str, asyncssh.SSHClientConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _conn_count(self, target: SSHTarget) -> int:
        return 1 if target.key() in self._conns else 0

    async def _get(self, target: SSHTarget) -> asyncssh.SSHClientConnection:
        key = target.key()
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            existing = self._conns.get(key)
            if existing is not None and not existing.is_closed():
                return existing
            kwargs: dict[str, Any] = {
                "host": target.host,
                "port": target.port,
                "username": target.user,
                "known_hosts": None,
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
        conn = await self._get(target)
        try:
            result = await conn.run(command, check=False)
        except (OSError, asyncssh.Error) as exc:
            raise UpstreamError(f"ssh exec failed: {exc}") from exc
        return CommandResult(
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
            exit_status=result.exit_status,
        )

    async def stream(self, target: SSHTarget, command: str):
        """Yield (channel, line) tuples interleaved from stdout and stderr until the process exits.

        Both streams are drained concurrently to avoid deadlock when the remote
        process produces output on both channels and one fills its window.
        """
        conn = await self._get(target)
        try:
            proc = await conn.create_process(command)
        except (OSError, asyncssh.Error) as exc:
            raise UpstreamError(f"ssh exec failed: {exc}") from exc

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
