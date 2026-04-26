"""GET / PUT /recipes/{name}/raw + form-based PUT preserves upstream-format fields."""

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


UPSTREAM_YAML = """recipe_version: 1
name: r1
description: original
model: org/model
defaults:
  tensor_parallel: 2
  gpu_memory_utilization: 0.92
command: |
  vllm serve {model}
"""


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    monkeypatch.setattr("sparkd.secrets._backend_get", lambda svc, k: None)
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


async def test_get_raw_returns_yaml_text(client):
    c, app = client
    app.state.library.save_recipe_raw("r1", UPSTREAM_YAML)
    r = await c.get("/api/recipes/r1/raw")
    assert r.status_code == 200
    assert r.json() == {"name": "r1", "yaml": UPSTREAM_YAML}


async def test_put_raw_overwrites_yaml(client):
    c, app = client
    app.state.library.save_recipe_raw("r1", UPSTREAM_YAML)
    new_yaml = "name: r1\nmodel: other/m\n"
    r = await c.put("/api/recipes/r1/raw", json={"yaml": new_yaml})
    assert r.status_code == 200
    assert r.json()["model"] == "other/m"
    assert app.state.library.load_recipe_text("r1") == new_yaml


async def test_form_put_preserves_upstream_fields(client):
    c, app = client
    app.state.library.save_recipe_raw("r1", UPSTREAM_YAML)
    r = await c.put(
        "/api/recipes/r1",
        json={
            "name": "r1",
            "model": "org/model",
            "description": "edited",
            "args": {"--max-model-len": "4096"},
            "env": {},
            "mods": [],
        },
    )
    assert r.status_code == 200
    raw = app.state.library.load_recipe_text("r1")
    # Form fields updated
    assert "description: edited" in raw
    assert "max-model-len" in raw
    # Upstream-only fields preserved
    assert "recipe_version" in raw
    assert "defaults" in raw
    assert "command" in raw
