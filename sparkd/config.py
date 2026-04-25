from __future__ import annotations

import tomllib
from dataclasses import dataclass

from sparkd import paths


@dataclass(frozen=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    advisor_provider: str = "anthropic"
    log_retention_days: int = 30


def load() -> AppConfig:
    cfg_path = paths.config_file()
    if not cfg_path.exists():
        return AppConfig()
    raw = tomllib.loads(cfg_path.read_text())
    server = raw.get("server", {})
    advisor = raw.get("advisor", {})
    return AppConfig(
        host=server.get("host", "127.0.0.1"),
        port=server.get("port", 8765),
        advisor_provider=advisor.get("provider", "anthropic"),
        log_retention_days=raw.get("log_retention_days", 30),
    )
