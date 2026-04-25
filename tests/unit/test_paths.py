from pathlib import Path

import pytest

from sparkd import paths


def test_root_defaults_to_home_sparkd(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SPARKD_HOME", raising=False)
    assert paths.root() == tmp_path / ".sparkd"


def test_root_honors_sparkd_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path / "elsewhere"))
    assert paths.root() == tmp_path / "elsewhere"


def test_ensure_creates_subdirs(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path / "h"))
    paths.ensure()
    for sub in ["library/recipes", "library/mods", "boxes", "logs"]:
        assert (tmp_path / "h" / sub).is_dir()


def test_state_db_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path / "h"))
    assert paths.state_db() == tmp_path / "h" / "state.db"
