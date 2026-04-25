from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import asyncssh


@dataclass
class FakeBox:
    """In-process SSH server for tests. Maps command → (stdout, stderr, exit_status)."""
    handlers: dict[str, tuple[str, str, int]] = field(default_factory=dict)
    received: list[str] = field(default_factory=list)
    streaming: dict[str, Callable[[asyncssh.SSHServerProcess], Any]] = field(default_factory=dict)

    def reply(self, cmd: str, stdout: str = "", stderr: str = "", exit: int = 0) -> None:
        self.handlers[cmd] = (stdout, stderr, exit)

    def stream(self, cmd: str, fn: Callable[[asyncssh.SSHServerProcess], Any]) -> None:
        self.streaming[cmd] = fn


class _Server(asyncssh.SSHServer):
    def begin_auth(self, username: str) -> bool:
        return False  # accept all


async def _process(box: FakeBox, process: asyncssh.SSHServerProcess) -> None:
    cmd = process.command or ""
    box.received.append(cmd)
    if cmd in box.streaming:
        await box.streaming[cmd](process)
        process.exit(0)
        return
    out, err, code = box.handlers.get(cmd, ("", f"unknown command: {cmd}\n", 127))
    if out:
        process.stdout.write(out)
    if err:
        process.stderr.write(err)
    process.exit(code)


async def start_fake_box(box: FakeBox, host: str = "127.0.0.1", port: int = 0) -> tuple[asyncssh.SSHAcceptor, int]:
    server = await asyncssh.create_server(
        _Server,
        host,
        port,
        server_host_keys=[asyncssh.generate_private_key("ssh-rsa")],
        process_factory=lambda p: asyncio.create_task(_process(box, p)),
    )
    sockets = server.sockets
    actual_port = sockets[0].getsockname()[1]
    return server, actual_port
