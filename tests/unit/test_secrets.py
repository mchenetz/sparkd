from sparkd import secrets as sec


def test_set_then_get_secret(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(sec, "_backend_set", lambda svc, k, v: store.__setitem__((svc, k), v))
    monkeypatch.setattr(sec, "_backend_get", lambda svc, k: store.get((svc, k)))
    monkeypatch.setattr(sec, "_backend_delete", lambda svc, k: store.pop((svc, k), None))

    sec.set_secret("anthropic_api_key", "sk-test")
    assert sec.get_secret("anthropic_api_key") == "sk-test"


def test_get_missing_returns_none(monkeypatch):
    monkeypatch.setattr(sec, "_backend_get", lambda svc, k: None)
    assert sec.get_secret("nonexistent") is None


def test_delete_secret(monkeypatch):
    store = {("sparkd", "x"): "v"}
    monkeypatch.setattr(sec, "_backend_set", lambda svc, k, v: store.__setitem__((svc, k), v))
    monkeypatch.setattr(sec, "_backend_get", lambda svc, k: store.get((svc, k)))
    monkeypatch.setattr(sec, "_backend_delete", lambda svc, k: store.pop((svc, k), None))

    sec.delete_secret("x")
    assert sec.get_secret("x") is None
