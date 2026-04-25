from __future__ import annotations

import click
import uvicorn

from sparkd import paths
from sparkd.config import load


@click.group()
def main() -> None:
    """sparkd — DGX Spark vLLM dashboard."""


@main.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve(host: str | None, port: int | None) -> None:
    """Run the localhost dashboard."""
    paths.ensure()
    cfg = load()
    uvicorn.run(
        "sparkd.app:build_app",
        host=host or cfg.host,
        port=port or cfg.port,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
