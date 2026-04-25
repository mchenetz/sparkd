import os
from pathlib import Path


def root() -> Path:
    override = os.environ.get("SPARKD_HOME")
    if override:
        return Path(override)
    return Path.home() / ".sparkd"


def state_db() -> Path:
    return root() / "state.db"


def library() -> Path:
    return root() / "library"


def boxes_dir() -> Path:
    return root() / "boxes"


def logs_dir() -> Path:
    return root() / "logs"


def config_file() -> Path:
    return root() / "config.toml"


def ensure() -> None:
    for sub in ["library/recipes", "library/mods", "boxes", "logs"]:
        (root() / sub).mkdir(parents=True, exist_ok=True)
