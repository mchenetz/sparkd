from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import AsyncIterator
from dataclasses import dataclass

import asyncssh


@dataclass
class ProbeResult:
    host: str
    port: int
    reachable: bool
    is_dgx_spark: bool = False
    gpu_line: str = ""
    error: str | None = None


async def _tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def probe_host(
    host: str,
    port: int = 22,
    *,
    user: str = "ubuntu",
    password: str | None = None,
    ssh_key_path: str | None = None,
    use_agent: bool = True,
    timeout: float = 3.0,
) -> ProbeResult:
    if not await _tcp_open(host, port, timeout):
        return ProbeResult(host=host, port=port, reachable=False)
    kwargs: dict = {
        "host": host,
        "port": port,
        "username": user,
        "known_hosts": None,
        "connect_timeout": timeout,
    }
    if password is not None:
        kwargs["password"] = password
        kwargs["client_keys"] = None
    elif ssh_key_path:
        kwargs["client_keys"] = [ssh_key_path]
    try:
        async with asyncssh.connect(**kwargs) as conn:
            res = await conn.run("nvidia-smi -L", check=False)
            line = (res.stdout or "").strip().splitlines()[:1]
            gpu_line = line[0] if line else ""
            return ProbeResult(
                host=host,
                port=port,
                reachable=True,
                is_dgx_spark="GB10" in gpu_line,
                gpu_line=gpu_line,
            )
    except (OSError, asyncssh.Error) as exc:
        return ProbeResult(
            host=host, port=port, reachable=True, error=str(exc)
        )


async def scan_subnet(
    cidr: str,
    *,
    user: str,
    ssh_key_path: str | None = None,
    use_agent: bool = True,
    concurrency: int = 32,
    timeout: float = 3.0,
) -> AsyncIterator[ProbeResult]:
    net = ipaddress.ip_network(cidr, strict=False)
    sem = asyncio.Semaphore(concurrency)

    async def worker(addr: str) -> ProbeResult:
        async with sem:
            return await probe_host(
                addr, user=user, ssh_key_path=ssh_key_path,
                use_agent=use_agent, timeout=timeout,
            )

    tasks = [asyncio.create_task(worker(str(ip))) for ip in net.hosts()]
    for t in asyncio.as_completed(tasks):
        yield await t
