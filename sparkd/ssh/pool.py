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
    exit_status: int


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
            conn = self._conns.get(key)
            if conn is not None and not conn.is_closed():
                return conn
            try:
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
                conn = await asyncssh.connect(**kwargs)
            except (OSError, asyncssh.Error) as exc:
                raise UpstreamError(f"ssh connect failed: {exc}") from exc
            self._conns[key] = conn
            return conn

    async def run(self, target: SSHTarget, command: str) -> CommandResult:
        conn = await self._get(target)
        try:
            result = await conn.run(command, check=False)
        except asyncssh.Error as exc:
            raise UpstreamError(f"ssh exec failed: {exc}") from exc
        return CommandResult(
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
            exit_status=result.exit_status or 0,
        )

    async def stream(self, target: SSHTarget, command: str):
        """Yield (channel, line) tuples until the process exits."""
        conn = await self._get(target)
        proc = await conn.create_process(command)
        async for line in proc.stdout:
            yield "stdout", line
        async for line in proc.stderr:
            yield "stderr", line
        await proc.wait()

    async def close(self, target: SSHTarget) -> None:
        key = target.key()
        conn = self._conns.pop(key, None)
        if conn is not None:
            conn.close()
            await conn.wait_closed()

    async def close_all(self) -> None:
        for conn in list(self._conns.values()):
            conn.close()
        for conn in list(self._conns.values()):
            await conn.wait_closed()
        self._conns.clear()
