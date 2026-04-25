from sparkd.config import AppConfig, load


def test_load_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    cfg = load()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765
    assert cfg.advisor_provider == "anthropic"


def test_load_reads_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "config.toml").write_text(
        '[server]\nport = 9000\n[advisor]\nprovider = "fake"\n'
    )
    cfg = load()
    assert cfg.port == 9000
    assert cfg.advisor_provider == "fake"
