import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkd.errors import (
    DomainError,
    NotFoundError,
    ValidationError,
    install_handlers,
)


@pytest.fixture
def client():
    app = FastAPI()
    install_handlers(app)

    @app.get("/notfound")
    def notfound():
        raise NotFoundError("box", "abc")

    @app.get("/invalid")
    def invalid():
        raise ValidationError("bad input", details={"field": "host"})

    return TestClient(app)


def test_notfound_returns_404_problem(client):
    r = client.get("/notfound")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Not Found"
    assert body["detail"] == "box 'abc' not found"


def test_validation_returns_422_with_details(client):
    r = client.get("/invalid")
    assert r.status_code == 422
    body = r.json()
    assert body["title"] == "Validation Error"
    assert body["details"] == {"field": "host"}


def test_domainerror_subclass_uses_status():
    class MyErr(DomainError):
        status = 418
        title = "Teapot"

    e = MyErr("brewing")
    assert e.status == 418
    assert e.title == "Teapot"
    assert e.detail == "brewing"
