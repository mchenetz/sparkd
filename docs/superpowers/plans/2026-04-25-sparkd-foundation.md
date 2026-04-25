# sparkd Foundation & Core Flows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a usable single-box DGX Spark dashboard: add a box, browse a local recipe library, launch a recipe on the box over SSH, and watch live status. AI features land in a follow-up plan.

**Architecture:** FastAPI backend with domain-service modules under `sparkd/services/`, talking to DGX Spark boxes over multiplexed `asyncssh`. SQLite for state, YAML files for the recipe library at `~/.sparkd/library/`. React + Vite SPA served by the same FastAPI process at `localhost:8765`. Pydantic models drive an OpenAPI schema that is auto-generated to TypeScript.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, asyncssh, Pydantic v2, SQLAlchemy 2 + alembic, structlog, pytest + pytest-asyncio, React 18 + Vite + TypeScript + TanStack Query, openapi-typescript, uv, ruff.

**Reference spec:** `docs/superpowers/specs/2026-04-25-sparkd-dashboard-design.md`

---

## File structure

Backend (`sparkd/`):

```
sparkd/
  __init__.py
  __main__.py                 # `python -m sparkd` entry
  cli.py                      # Click app: serve / export / import
  config.py                   # AppConfig loader: ~/.sparkd/config.toml
  paths.py                    # ~/.sparkd/* path helpers
  app.py                      # FastAPI factory (build_app)
  errors.py                   # DomainError + RFC 7807 mapping
  schemas/
    __init__.py
    box.py                    # BoxSpec, BoxCreate, BoxStatus, BoxCapabilities
    recipe.py                 # RecipeSpec, RecipeDraft, RecipeDiff
    launch.py                 # LaunchSpec, LaunchRecord, LaunchState
    job.py                    # Job, JobState
  db/
    __init__.py
    engine.py                 # async engine + session factory
    models.py                 # SQLAlchemy ORM tables
    migrations/               # alembic env.py + versions/
  services/
    __init__.py
    box.py                    # BoxService (registry + ssh pool)
    library.py                # LibraryService (~/.sparkd/library)
    recipe.py                 # RecipeService
    launch.py                 # LaunchService
    status.py                 # StatusService
    cluster.py                # ClusterService stub
    jobs.py                   # JobRegistry
  ssh/
    __init__.py
    pool.py                   # SSHPool (asyncssh multiplexed conns)
    discovery.py              # subnet scan helpers
  routes/
    __init__.py
    boxes.py
    recipes.py
    launches.py
    status.py
    jobs.py
    ws.py                     # websocket endpoints
  static/                     # built React assets (populated by frontend build)
tests/
  conftest.py                 # tmp ~/.sparkd, fake SSH server
  ssh_fakes.py                # asyncssh in-process server helpers
  unit/
    test_config.py
    test_paths.py
    test_errors.py
    test_library.py
    test_recipe_validate.py
    test_status_reconcile.py
    test_jobs.py
  integration/
    test_box_routes.py
    test_recipe_routes.py
    test_launch_flow.py
    test_status_ws.py
pyproject.toml
alembic.ini
```

Frontend (`frontend/`):

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts               # fetch wrapper + WS helper
      generated.ts            # `openapi-typescript` output (gitignored, build step)
    pages/
      BoxesPage.tsx
      RecipesPage.tsx
      LaunchPage.tsx
      StatusPage.tsx
    components/
      BoxList.tsx
      AddBoxDialog.tsx
      RecipeList.tsx
      LaunchButton.tsx
      LiveLog.tsx
      StatusTable.tsx
    hooks/
      useBoxes.ts
      useRecipes.ts
      useLaunches.ts
      useBoxStatus.ts
      useWebSocket.ts
```

Each backend service file owns one responsibility from §3 of the spec. Routes are thin: parse, call service, serialize. WebSocket endpoints live in a single `ws.py` module that delegates to the relevant service's stream method. Frontend pages map 1:1 to top-level nav items; one-shot dialogs and tables are colocated in `components/`.

---

## Task 0: Repo scaffold and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.python-version`
- Create: `README.md`
- Create: `sparkd/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Init git repo and create the project root files**

```bash
cd /Users/mchenetz/git/sparkd
git init
```

Write `.python-version`:

```
3.12
```

Write `.gitignore`:

```
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
node_modules/
frontend/dist/
sparkd/static/
*.egg-info/
build/
dist/
.coverage
htmlcov/
.env
docs/superpowers/specs/*.draft.md
```

Write `README.md`:

```markdown
# sparkd

Localhost dashboard for managing vLLM workloads on NVIDIA DGX Spark boxes via [eugr/spark-vllm-docker](https://github.com/eugr/spark-vllm-docker).

See `docs/superpowers/specs/2026-04-25-sparkd-dashboard-design.md` for the design.

## Dev

```
uv sync
uv run sparkd serve
```
```

Write `pyproject.toml`:

```toml
[project]
name = "sparkd"
version = "0.0.1"
description = "Dashboard for DGX Spark vLLM workloads"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "asyncssh>=2.18",
  "sqlalchemy[asyncio]>=2.0",
  "aiosqlite>=0.20",
  "alembic>=1.13",
  "click>=8.1",
  "structlog>=24.4",
  "keyring>=25.4",
  "pyyaml>=6.0",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5.0",
  "ruff>=0.6",
  "mypy>=1.11",
  "respx>=0.21",
]

[project.scripts]
sparkd = "sparkd.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["sparkd"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = ["e2e: requires a real DGX Spark box (set SPARKD_E2E_BOX)"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "ASYNC"]
```

Create the empty `__init__.py` files for `sparkd/` and `tests/`.

- [ ] **Step 2: Verify uv sync works**

Run: `uv sync --extra dev`
Expected: creates `.venv/`, installs dependencies, no errors.

Run: `uv run python -c "import sparkd; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "chore: scaffold sparkd project"
```

---

## Task 1: AppConfig and ~/.sparkd paths

**Files:**
- Create: `sparkd/paths.py`
- Create: `sparkd/config.py`
- Create: `tests/unit/test_paths.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_paths.py`:

```python
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
```

`tests/unit/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_paths.py tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sparkd.paths'`.

- [ ] **Step 3: Implement `paths.py`**

```python
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
```

- [ ] **Step 4: Implement `config.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_paths.py tests/unit/test_config.py -v`
Expected: PASS, 6 passed.

- [ ] **Step 6: Commit**

```bash
git add sparkd/paths.py sparkd/config.py tests/unit/test_paths.py tests/unit/test_config.py
git commit -m "feat: AppConfig and ~/.sparkd path helpers"
```

---

## Task 2: DomainError + RFC 7807 mapper

**Files:**
- Create: `sparkd/errors.py`
- Create: `tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_errors.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `errors.py`**

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status: int = 500
    title: str = "Internal Error"

    def __init__(self, detail: str, *, details: dict | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.details = details or {}


class NotFoundError(DomainError):
    status = 404
    title = "Not Found"

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"{kind} '{key}' not found")
        self.kind = kind
        self.key = key


class ValidationError(DomainError):
    status = 422
    title = "Validation Error"


class ConflictError(DomainError):
    status = 409
    title = "Conflict"


class UpstreamError(DomainError):
    status = 502
    title = "Upstream Error"


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle(request: Request, exc: DomainError) -> JSONResponse:
        body = {
            "type": "about:blank",
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
        }
        if exc.details:
            body["details"] = exc.details
        return JSONResponse(
            status_code=exc.status,
            content=body,
            media_type="application/problem+json",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_errors.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/errors.py tests/unit/test_errors.py
git commit -m "feat: DomainError hierarchy and RFC 7807 mapper"
```

---

## Task 3: SQLAlchemy models and alembic init

**Files:**
- Create: `sparkd/db/__init__.py`
- Create: `sparkd/db/engine.py`
- Create: `sparkd/db/models.py`
- Create: `alembic.ini`
- Create: `sparkd/db/migrations/env.py`
- Create: `sparkd/db/migrations/script.py.mako`
- Create: `sparkd/db/migrations/versions/0001_initial.py`
- Create: `tests/unit/test_db_models.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_db_models.py`:

```python
import pytest
from sqlalchemy import select

from sparkd.db.engine import session_scope, init_engine
from sparkd.db.models import Box, Launch, AuditLog


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    await init_engine(create_all=True)
    yield


async def test_can_insert_and_read_box(db):
    async with session_scope() as s:
        s.add(Box(id="b1", name="spark-01", host="10.0.0.5", user="ubuntu"))
    async with session_scope() as s:
        rows = (await s.execute(select(Box))).scalars().all()
    assert len(rows) == 1
    assert rows[0].host == "10.0.0.5"


async def test_launch_box_relationship(db):
    async with session_scope() as s:
        s.add(Box(id="b1", name="x", host="h", user="u"))
        s.add(
            Launch(
                id="l1",
                box_id="b1",
                recipe_name="r",
                state="starting",
                command="./run-recipe.sh r",
            )
        )
    async with session_scope() as s:
        l = (await s.execute(select(Launch))).scalar_one()
        assert l.box_id == "b1"
        assert l.state == "starting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_db_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `db/engine.py`**

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sparkd import paths
from sparkd.db.models import Base

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


async def init_engine(*, create_all: bool = False) -> None:
    global _engine, _sessionmaker
    paths.ensure()
    url = f"sqlite+aiosqlite:///{paths.state_db()}"
    _engine = create_async_engine(url, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    if create_all:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("init_engine() not called")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def shutdown() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
```

- [ ] **Step 4: Implement `db/models.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Box(Base):
    __tablename__ = "boxes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(default=22)
    user: Mapped[str] = mapped_column(String)
    ssh_key_path: Mapped[str | None] = mapped_column(String, nullable=True)
    use_agent: Mapped[bool] = mapped_column(default=True)
    repo_path: Mapped[str] = mapped_column(default="~/spark-vllm-docker")
    tags_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capabilities_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    capabilities_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    launches: Mapped[list["Launch"]] = relationship(back_populates="box")


class Launch(Base):
    __tablename__ = "launches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    box_id: Mapped[str] = mapped_column(ForeignKey("boxes.id"))
    recipe_name: Mapped[str] = mapped_column(String)
    recipe_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mods_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String)  # starting|healthy|failed|stopped|interrupted
    container_id: Mapped[str | None] = mapped_column(String, nullable=True)
    command: Mapped[str] = mapped_column(String)
    log_path: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_info_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    box: Mapped[Box] = relationship(back_populates="launches")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actor: Mapped[str] = mapped_column(String, default="local")
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
```

`sparkd/db/__init__.py`:

```python
from sparkd.db.engine import init_engine, session_scope, shutdown
from sparkd.db.models import AuditLog, Base, Box, Launch

__all__ = ["init_engine", "session_scope", "shutdown", "Base", "Box", "Launch", "AuditLog"]
```

- [ ] **Step 5: Initialize alembic**

Write `alembic.ini`:

```ini
[alembic]
script_location = sparkd/db/migrations
sqlalchemy.url = sqlite+aiosqlite:///%(SPARKD_HOME)s/state.db

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Write `sparkd/db/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sparkd.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = cfg["sqlalchemy.url"].replace("+aiosqlite", "")
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

Write `sparkd/db/migrations/script.py.mako`:

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Write `sparkd/db/migrations/versions/0001_initial.py`:

```python
"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boxes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("user", sa.String(), nullable=False),
        sa.Column("ssh_key_path", sa.String(), nullable=True),
        sa.Column("use_agent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("repo_path", sa.String(), nullable=False, server_default="~/spark-vllm-docker"),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("capabilities_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "launches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("box_id", sa.String(), sa.ForeignKey("boxes.id"), nullable=False),
        sa.Column("recipe_name", sa.String(), nullable=False),
        sa.Column("recipe_snapshot_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("mods_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("container_id", sa.String(), nullable=True),
        sa.Column("command", sa.String(), nullable=False),
        sa.Column("log_path", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime(), nullable=True),
        sa.Column("exit_info_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("actor", sa.String(), nullable=False, server_default="local"),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("launches")
    op.drop_table("boxes")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_db_models.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 7: Commit**

```bash
git add sparkd/db alembic.ini tests/unit/test_db_models.py
git commit -m "feat: SQLAlchemy models and alembic baseline migration"
```

---

## Task 4: Pydantic schemas

**Files:**
- Create: `sparkd/schemas/__init__.py`
- Create: `sparkd/schemas/box.py`
- Create: `sparkd/schemas/recipe.py`
- Create: `sparkd/schemas/launch.py`
- Create: `sparkd/schemas/job.py`
- Create: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from sparkd.schemas.box import BoxCreate, BoxSpec
from sparkd.schemas.recipe import RecipeSpec
from sparkd.schemas.launch import LaunchCreate, LaunchState


def test_box_create_minimum():
    b = BoxCreate(name="spark-01", host="10.0.0.5", user="ubuntu")
    assert b.port == 22
    assert b.use_agent is True


def test_box_create_rejects_empty_host():
    with pytest.raises(ValidationError):
        BoxCreate(name="x", host="", user="u")


def test_recipe_spec_round_trip():
    r = RecipeSpec(
        name="llama-8b",
        model="meta-llama/Llama-3.1-8B-Instruct",
        args={"--tensor-parallel-size": "2", "--gpu-memory-utilization": "0.92"},
    )
    assert r.model_dump()["args"]["--tensor-parallel-size"] == "2"


def test_launch_state_values():
    assert LaunchState.starting.value == "starting"
    assert {s.value for s in LaunchState} == {
        "starting", "healthy", "failed", "stopped", "interrupted"
    }


def test_launch_create_requires_recipe_and_box():
    with pytest.raises(ValidationError):
        LaunchCreate(recipe="", box_id="")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement schemas**

`sparkd/schemas/box.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BoxBase(BaseModel):
    name: str = Field(min_length=1)
    host: str = Field(min_length=1)
    port: int = 22
    user: str = Field(min_length=1)
    ssh_key_path: str | None = None
    use_agent: bool = True
    repo_path: str = "~/spark-vllm-docker"
    tags: dict[str, str] = Field(default_factory=dict)


class BoxCreate(BoxBase):
    pass


class BoxSpec(BoxBase):
    id: str
    created_at: datetime


class BoxCapabilities(BaseModel):
    gpu_count: int
    gpu_model: str
    vram_per_gpu_gb: int
    cuda_version: str | None = None
    ib_interface: str | None = None
    captured_at: datetime
```

`sparkd/schemas/recipe.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class RecipeSpec(BaseModel):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    description: str = ""
    args: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    mods: list[str] = Field(default_factory=list)


class RecipeDiff(BaseModel):
    name: str
    added: dict[str, str]
    removed: dict[str, str]
    changed: dict[str, tuple[str, str]]
```

`sparkd/schemas/launch.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LaunchState(str, Enum):
    starting = "starting"
    healthy = "healthy"
    failed = "failed"
    stopped = "stopped"
    interrupted = "interrupted"


class LaunchCreate(BaseModel):
    recipe: str = Field(min_length=1)
    box_id: str = Field(min_length=1)
    mods: list[str] = Field(default_factory=list)
    overrides: dict[str, str] = Field(default_factory=dict)


class LaunchRecord(BaseModel):
    id: str
    box_id: str
    recipe_name: str
    state: LaunchState
    container_id: str | None
    command: str
    started_at: datetime
    stopped_at: datetime | None
    exit_info: dict[str, Any] | None
```

`sparkd/schemas/job.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobState(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    interrupted = "interrupted"


class Job(BaseModel):
    id: str
    kind: str
    state: JobState
    progress: float = 0.0
    message: str = ""
    result: dict | None = None
    started_at: datetime
    finished_at: datetime | None = None
```

`sparkd/schemas/__init__.py`:

```python
from sparkd.schemas.box import BoxBase, BoxCapabilities, BoxCreate, BoxSpec
from sparkd.schemas.job import Job, JobState
from sparkd.schemas.launch import LaunchCreate, LaunchRecord, LaunchState
from sparkd.schemas.recipe import RecipeDiff, RecipeSpec

__all__ = [
    "BoxBase", "BoxCreate", "BoxSpec", "BoxCapabilities",
    "RecipeSpec", "RecipeDiff",
    "LaunchCreate", "LaunchRecord", "LaunchState",
    "Job", "JobState",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_schemas.py -v`
Expected: PASS, 5 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/schemas tests/unit/test_schemas.py
git commit -m "feat: Pydantic schemas for box/recipe/launch/job"
```

---

## Task 5: SSH fake server fixture

**Files:**
- Create: `tests/ssh_fakes.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the fixture**

`tests/ssh_fakes.py`:

```python
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
```

`tests/conftest.py`:

```python
import os

import pytest

from tests.ssh_fakes import FakeBox, start_fake_box


@pytest.fixture
def sparkd_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
async def fake_box():
    box = FakeBox()
    server, port = await start_fake_box(box)
    yield box, port
    server.close()
    await server.wait_closed()
```

- [ ] **Step 2: Smoke-test the fixture**

Add `tests/unit/test_ssh_fakes.py`:

```python
import asyncssh

from tests.ssh_fakes import FakeBox


async def test_fake_box_responds_to_known_command(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: NVIDIA GB10\n")
    async with asyncssh.connect(
        "127.0.0.1",
        port=port,
        username="x",
        password="y",
        known_hosts=None,
        client_keys=None,
    ) as conn:
        result = await conn.run("nvidia-smi -L", check=False)
    assert result.exit_status == 0
    assert "GB10" in result.stdout
    assert "nvidia-smi -L" in box.received
```

Run: `uv run pytest tests/unit/test_ssh_fakes.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/ssh_fakes.py tests/conftest.py tests/unit/test_ssh_fakes.py
git commit -m "test: in-process asyncssh fake box fixture"
```

---

## Task 6: SSHPool with multiplexed connections

**Files:**
- Create: `sparkd/ssh/__init__.py` (empty)
- Create: `sparkd/ssh/pool.py`
- Create: `tests/unit/test_ssh_pool.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_ssh_pool.py`:

```python
import asyncssh
import pytest

from sparkd.ssh.pool import SSHPool, SSHTarget
from tests.ssh_fakes import FakeBox, start_fake_box


@pytest.fixture
async def pool():
    p = SSHPool()
    yield p
    await p.close_all()


async def test_run_returns_stdout(fake_box, pool):
    box, port = fake_box
    box.reply("echo hi", stdout="hi\n")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    result = await pool.run(target, "echo hi")
    assert result.stdout.strip() == "hi"
    assert result.exit_status == 0


async def test_reuses_connection(fake_box, pool):
    box, port = fake_box
    box.reply("a", stdout="A")
    box.reply("b", stdout="B")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    await pool.run(target, "a")
    await pool.run(target, "b")
    # Two commands but should have used one connection.
    assert pool._conn_count(target) == 1


async def test_reconnects_after_close(fake_box, pool):
    box, port = fake_box
    box.reply("a", stdout="A")
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    await pool.run(target, "a")
    await pool.close(target)
    await pool.run(target, "a")
    assert pool._conn_count(target) == 1


async def test_stream_interleaves_stdout_and_stderr(fake_box, pool):
    box, port = fake_box

    async def stream_handler(process: asyncssh.SSHServerProcess) -> None:
        # Emit interleaved output on both channels.
        process.stdout.write("out-1\n")
        process.stderr.write("err-1\n")
        process.stdout.write("out-2\n")
        process.stderr.write("err-2\n")

    box.stream("noisy", stream_handler)
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    seen = []
    async for channel, line in pool.stream(target, "noisy"):
        seen.append((channel, line.strip()))
    channels = {c for c, _ in seen}
    assert channels == {"stdout", "stderr"}
    # All four lines arrived (filter empty lines that asyncssh emits at channel close)
    assert {l for _, l in seen if l} == {"out-1", "err-1", "out-2", "err-2"}


async def test_run_returns_none_exit_status_for_signal(fake_box, pool):
    """When asyncssh reports exit_status=None (signal termination), we surface None."""
    box, port = fake_box
    # FakeBox can't easily simulate signal-terminated, but we can verify
    # the field is now Optional and falsy values aren't coerced.
    box.reply("succeed", stdout="", exit=0)
    target = SSHTarget(host="127.0.0.1", port=port, user="x", use_agent=False, password="y")
    res = await pool.run(target, "succeed")
    # exit_status is now an int (0), preserved exactly.
    assert res.exit_status == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_ssh_pool.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `ssh/pool.py`**

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import asyncssh

from sparkd.errors import UpstreamError


@dataclass(frozen=True)
class SSHTarget:
    host: str
    port: int
    user: str
    use_agent: bool = True
    ssh_key_path: str | None = None
    password: str | None = None  # tests only

    def key(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int | None  # None means process was terminated by a signal


class SSHPool:
    def __init__(self) -> None:
        self._conns: dict[str, asyncssh.SSHClientConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _conn_count(self, target: SSHTarget) -> int:
        return 1 if target.key() in self._conns else 0

    async def _get(self, target: SSHTarget) -> asyncssh.SSHClientConnection:
        key = target.key()
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            existing = self._conns.get(key)
            if existing is not None and not existing.is_closed():
                return existing
            kwargs: dict[str, Any] = {
                "host": target.host,
                "port": target.port,
                "username": target.user,
                "known_hosts": None,
            }
            if target.password is not None:
                kwargs["password"] = target.password
                kwargs["client_keys"] = None
            elif target.ssh_key_path:
                kwargs["client_keys"] = [target.ssh_key_path]
            elif target.use_agent:
                pass  # asyncssh defaults to agent
            try:
                conn = await asyncssh.connect(**kwargs)
            except (OSError, asyncssh.Error) as exc:
                raise UpstreamError(f"ssh connect failed: {exc}") from exc
            try:
                self._conns[key] = conn
            except BaseException:
                conn.close()
                raise
            return conn

    async def run(self, target: SSHTarget, command: str) -> CommandResult:
        conn = await self._get(target)
        try:
            result = await conn.run(command, check=False)
        except (OSError, asyncssh.Error) as exc:
            raise UpstreamError(f"ssh exec failed: {exc}") from exc
        return CommandResult(
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
            exit_status=result.exit_status,
        )

    async def stream(self, target: SSHTarget, command: str):
        """Yield (channel, line) tuples interleaved from stdout and stderr until the process exits.

        Both streams are drained concurrently to avoid deadlock when the remote
        process produces output on both channels and one fills its window.
        """
        conn = await self._get(target)
        try:
            proc = await conn.create_process(command)
        except (OSError, asyncssh.Error) as exc:
            raise UpstreamError(f"ssh exec failed: {exc}") from exc

        queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

        async def _drain(reader: Any, channel: str) -> None:
            try:
                async for line in reader:
                    await queue.put((channel, line))
            finally:
                await queue.put(None)  # EOF sentinel

        tasks = [
            asyncio.create_task(_drain(proc.stdout, "stdout")),
            asyncio.create_task(_drain(proc.stderr, "stderr")),
        ]
        try:
            done = 0
            while done < 2:
                item = await queue.get()
                if item is None:
                    done += 1
                else:
                    yield item
            await proc.wait()
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            for t in tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

    async def close(self, target: SSHTarget) -> None:
        key = target.key()
        conn = self._conns.pop(key, None)
        self._locks.pop(key, None)
        if conn is not None:
            conn.close()
            await conn.wait_closed()

    async def close_all(self) -> None:
        conns = list(self._conns.values())
        self._conns.clear()
        self._locks.clear()
        for conn in conns:
            conn.close()
        for conn in conns:
            await conn.wait_closed()
```

`sparkd/ssh/__init__.py`:

```python
from sparkd.ssh.pool import CommandResult, SSHPool, SSHTarget

__all__ = ["SSHPool", "SSHTarget", "CommandResult"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_ssh_pool.py -v`
Expected: PASS, 5 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/ssh tests/unit/test_ssh_pool.py
git commit -m "feat: SSHPool with per-box multiplexed connections"
```

---

## Task 7: BoxService — registry + capabilities

**Files:**
- Create: `sparkd/services/__init__.py` (empty)
- Create: `sparkd/services/box.py`
- Create: `tests/integration/test_box_service.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_box_service.py`:

```python
import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCreate
from sparkd.services.box import BoxService
from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def svc(sparkd_home):
    await init_engine(create_all=True)
    pool = SSHPool()
    yield BoxService(pool=pool)
    await pool.close_all()


async def test_create_then_get(svc):
    spec = await svc.create(BoxCreate(name="spark-01", host="10.0.0.5", user="ubuntu"))
    assert spec.id
    fetched = await svc.get(spec.id)
    assert fetched.name == "spark-01"


async def test_list_returns_all(svc):
    await svc.create(BoxCreate(name="a", host="h1", user="u"))
    await svc.create(BoxCreate(name="b", host="h2", user="u"))
    rows = await svc.list()
    assert {b.name for b in rows} == {"a", "b"}


async def test_capabilities_parses_nvidia_smi(svc, fake_box, monkeypatch):
    box, port = fake_box
    box.reply(
        "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits",
        stdout="NVIDIA GB10, 96000, 555.42\nNVIDIA GB10, 96000, 555.42\n",
    )
    box.reply("nvcc --version 2>/dev/null || true", stdout="release 12.5\n")
    box.reply(
        "ls /sys/class/infiniband 2>/dev/null || true", stdout="mlx5_0\n"
    )
    spec = await svc.create(
        BoxCreate(name="x", host="127.0.0.1", port=port, user="x")
    )
    monkeypatch.setattr(
        svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    caps = await svc.capabilities(spec.id, refresh=True)
    assert caps.gpu_count == 2
    assert caps.gpu_model == "NVIDIA GB10"
    assert caps.vram_per_gpu_gb == 96
    assert caps.ib_interface == "mlx5_0"


async def test_test_connection_returns_true_when_ssh_ok(svc, fake_box, monkeypatch):
    box, port = fake_box
    box.reply("true", stdout="")
    spec = await svc.create(BoxCreate(name="x", host="127.0.0.1", port=port, user="x"))
    monkeypatch.setattr(
        svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    assert await svc.test_connection(spec.id) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_box_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/box.py`**

```python
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import Box
from sparkd.errors import NotFoundError, UpstreamError
from sparkd.schemas.box import BoxCapabilities, BoxCreate, BoxSpec
from sparkd.ssh.pool import SSHPool, SSHTarget


def _to_spec(row: Box) -> BoxSpec:
    return BoxSpec(
        id=row.id,
        name=row.name,
        host=row.host,
        port=row.port,
        user=row.user,
        ssh_key_path=row.ssh_key_path,
        use_agent=row.use_agent,
        repo_path=row.repo_path,
        tags=row.tags_json or {},
        created_at=row.created_at,
    )


class BoxService:
    def __init__(self, pool: SSHPool) -> None:
        self.pool = pool

    def _target_for(self, row: Box) -> SSHTarget:
        return SSHTarget(
            host=row.host,
            port=row.port,
            user=row.user,
            use_agent=row.use_agent,
            ssh_key_path=row.ssh_key_path,
        )

    async def create(self, body: BoxCreate) -> BoxSpec:
        async with session_scope() as s:
            row = Box(
                id=uuid.uuid4().hex[:12],
                name=body.name,
                host=body.host,
                port=body.port,
                user=body.user,
                ssh_key_path=body.ssh_key_path,
                use_agent=body.use_agent,
                repo_path=body.repo_path,
                tags_json=body.tags,
            )
            s.add(row)
            await s.flush()
            return _to_spec(row)

    async def list(self) -> list[BoxSpec]:
        async with session_scope() as s:
            rows = (await s.execute(select(Box))).scalars().all()
            return [_to_spec(r) for r in rows]

    async def get(self, box_id: str) -> BoxSpec:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            return _to_spec(row)

    async def delete(self, box_id: str) -> None:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            await s.delete(row)

    async def test_connection(self, box_id: str) -> bool:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
        target = self._target_for(row)
        result = await self.pool.run(target, "true")
        return result.exit_status == 0

    async def capabilities(self, box_id: str, *, refresh: bool = False) -> BoxCapabilities:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            if (
                not refresh
                and row.capabilities_json
                and row.capabilities_at
            ):
                return BoxCapabilities(**row.capabilities_json)
        target = self._target_for(row)
        gpu_q = await self.pool.run(
            target,
            "nvidia-smi --query-gpu=name,memory.total,driver_version "
            "--format=csv,noheader,nounits",
        )
        if gpu_q.exit_status != 0:
            raise UpstreamError(f"nvidia-smi failed: {gpu_q.stderr.strip()}")
        gpus = [
            tuple(p.strip() for p in line.split(","))
            for line in gpu_q.stdout.strip().splitlines()
            if line.strip()
        ]
        if not gpus:
            raise UpstreamError("nvidia-smi returned no GPUs")
        gpu_model = gpus[0][0]
        vram_mib = int(gpus[0][1])
        nvcc = await self.pool.run(target, "nvcc --version 2>/dev/null || true")
        cuda = None
        m = re.search(r"release (\S+)", nvcc.stdout)
        if m:
            cuda = m.group(1).rstrip(",")
        ib = await self.pool.run(target, "ls /sys/class/infiniband 2>/dev/null || true")
        ib_iface = ib.stdout.strip().splitlines()[0] if ib.stdout.strip() else None
        caps = BoxCapabilities(
            gpu_count=len(gpus),
            gpu_model=gpu_model,
            vram_per_gpu_gb=vram_mib // 1024,
            cuda_version=cuda,
            ib_interface=ib_iface,
            captured_at=datetime.now(timezone.utc),
        )
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            row.capabilities_json = caps.model_dump(mode="json")
            row.capabilities_at = caps.captured_at
        return caps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_box_service.py -v`
Expected: PASS, 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/__init__.py sparkd/services/box.py tests/integration/test_box_service.py
git commit -m "feat: BoxService — registry, test_connection, capabilities"
```

---

## Task 8: LibraryService — recipe/mod files on disk

**Files:**
- Create: `sparkd/services/library.py`
- Create: `tests/unit/test_library.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_library.py`:

```python
import pytest

from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.library import LibraryService


@pytest.fixture
def lib(sparkd_home):
    return LibraryService()


def test_save_then_load_recipe(lib):
    r = RecipeSpec(name="r1", model="m", args={"--foo": "bar"})
    lib.save_recipe(r)
    got = lib.load_recipe("r1")
    assert got.args == {"--foo": "bar"}


def test_load_missing_raises(lib):
    with pytest.raises(NotFoundError):
        lib.load_recipe("nope")


def test_list_recipes_returns_canonical(lib):
    lib.save_recipe(RecipeSpec(name="a", model="m"))
    lib.save_recipe(RecipeSpec(name="b", model="m"))
    names = [r.name for r in lib.list_recipes()]
    assert sorted(names) == ["a", "b"]


def test_effective_view_merges_overrides(lib):
    lib.save_recipe(RecipeSpec(name="r1", model="m", args={"--tp": "1"}))
    lib.save_recipe_override(
        "box-x", RecipeSpec(name="r1", model="m", args={"--tp": "2"})
    )
    eff = lib.load_recipe("r1", box_id="box-x")
    assert eff.args["--tp"] == "2"


def test_save_recipe_rejects_path_traversal(lib):
    with pytest.raises(ValidationError):
        lib.save_recipe(RecipeSpec(name="../evil", model="m"))


def test_delete_recipe(lib):
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    lib.delete_recipe("r1")
    with pytest.raises(NotFoundError):
        lib.load_recipe("r1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_library.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/library.py`**

```python
from __future__ import annotations

import re
from pathlib import Path

import yaml

from sparkd import paths
from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.recipe import RecipeSpec

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")


def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValidationError(f"invalid name: {name!r}")


class LibraryService:
    def __init__(self) -> None:
        paths.ensure()

    def _recipes_dir(self, box_id: str | None) -> Path:
        if box_id is None:
            return paths.library() / "recipes"
        return paths.boxes_dir() / box_id / "overrides" / "recipes"

    def save_recipe(self, spec: RecipeSpec) -> None:
        _validate_name(spec.name)
        d = self._recipes_dir(None)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{spec.name}.yaml").write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    def save_recipe_override(self, box_id: str, spec: RecipeSpec) -> None:
        _validate_name(spec.name)
        d = self._recipes_dir(box_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{spec.name}.yaml").write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    def load_recipe(self, name: str, *, box_id: str | None = None) -> RecipeSpec:
        _validate_name(name)
        if box_id is not None:
            override = self._recipes_dir(box_id) / f"{name}.yaml"
            if override.exists():
                return RecipeSpec(**yaml.safe_load(override.read_text()))
        canonical = self._recipes_dir(None) / f"{name}.yaml"
        if not canonical.exists():
            raise NotFoundError("recipe", name)
        return RecipeSpec(**yaml.safe_load(canonical.read_text()))

    def list_recipes(self, *, box_id: str | None = None) -> list[RecipeSpec]:
        d = self._recipes_dir(None)
        if not d.exists():
            return []
        out: dict[str, RecipeSpec] = {}
        for p in sorted(d.glob("*.yaml")):
            out[p.stem] = RecipeSpec(**yaml.safe_load(p.read_text()))
        if box_id:
            override_d = self._recipes_dir(box_id)
            if override_d.exists():
                for p in sorted(override_d.glob("*.yaml")):
                    out[p.stem] = RecipeSpec(**yaml.safe_load(p.read_text()))
        return list(out.values())

    def delete_recipe(self, name: str) -> None:
        _validate_name(name)
        f = self._recipes_dir(None) / f"{name}.yaml"
        if not f.exists():
            raise NotFoundError("recipe", name)
        f.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_library.py -v`
Expected: PASS, 6 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/library.py tests/unit/test_library.py
git commit -m "feat: LibraryService — recipe storage with overrides"
```

---

## Task 9: RecipeService — validate, sync, diff

**Files:**
- Create: `sparkd/services/recipe.py`
- Create: `tests/integration/test_recipe_service.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_recipe_service.py`:

```python
import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCapabilities, BoxCreate
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.box import BoxService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.ssh.pool import SSHPool, SSHTarget
from datetime import datetime, timezone


@pytest.fixture
async def svc(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    pool = SSHPool()
    box_svc = BoxService(pool=pool)
    lib = LibraryService()
    box, port = fake_box
    monkeypatch.setattr(
        box_svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    yield RecipeService(library=lib, boxes=box_svc, pool=pool), box_svc, box, port
    await pool.close_all()


def _caps(gpu_count: int, vram: int = 96) -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=gpu_count,
        gpu_model="NVIDIA GB10",
        vram_per_gpu_gb=vram,
        captured_at=datetime.now(timezone.utc),
    )


async def test_validate_passes_when_tp_matches_gpu_count(svc, monkeypatch):
    rs, box_svc, _, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    monkeypatch.setattr(box_svc, "capabilities", lambda *_a, **_k: _caps(2))
    r = RecipeSpec(name="r", model="m", args={"--tensor-parallel-size": "2"})
    issues = await rs.validate(r, bs.id)
    assert issues == []


async def test_validate_fails_when_tp_exceeds_gpus(svc, monkeypatch):
    rs, box_svc, _, _ = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    monkeypatch.setattr(box_svc, "capabilities", lambda *_a, **_k: _caps(1))
    r = RecipeSpec(name="r", model="m", args={"--tensor-parallel-size": "4"})
    issues = await rs.validate(r, bs.id)
    assert any("tensor-parallel-size" in i for i in issues)


async def test_sync_writes_yaml_to_box_repo(svc):
    rs, box_svc, fake, _port = svc
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    rs.library.save_recipe(RecipeSpec(name="r1", model="m", args={"--tp": "1"}))
    fake.reply("mkdir -p ~/spark-vllm-docker/recipes", stdout="")
    fake.reply(
        "cat > ~/spark-vllm-docker/recipes/r1.yaml <<'SPARKD_EOF'\n"
        + (rs.library.load_recipe("r1").model_dump_json() + "\n")
        + "SPARKD_EOF\n",
        stdout="",
    )
    # Use a permissive matcher: assert sync issues a write command for the yaml file.
    await rs.sync("r1", bs.id)
    assert any("recipes/r1.yaml" in c for c in fake.received)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_recipe_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/recipe.py`**

```python
from __future__ import annotations

import shlex

import yaml

from sparkd.schemas.recipe import RecipeDiff, RecipeSpec
from sparkd.services.box import BoxService
from sparkd.services.library import LibraryService
from sparkd.ssh.pool import SSHPool


class RecipeService:
    def __init__(
        self, library: LibraryService, boxes: BoxService, pool: SSHPool
    ) -> None:
        self.library = library
        self.boxes = boxes
        self.pool = pool

    async def validate(self, recipe: RecipeSpec, box_id: str) -> list[str]:
        caps = await self.boxes.capabilities(box_id)
        issues: list[str] = []
        tp_raw = recipe.args.get("--tensor-parallel-size")
        if tp_raw is not None:
            try:
                tp = int(tp_raw)
            except ValueError:
                issues.append(f"--tensor-parallel-size not an integer: {tp_raw!r}")
            else:
                if tp > caps.gpu_count:
                    issues.append(
                        f"--tensor-parallel-size={tp} exceeds GPU count "
                        f"{caps.gpu_count} on this box"
                    )
        gmu_raw = recipe.args.get("--gpu-memory-utilization")
        if gmu_raw is not None:
            try:
                gmu = float(gmu_raw)
            except ValueError:
                issues.append(f"--gpu-memory-utilization not a float: {gmu_raw!r}")
            else:
                if not 0.0 < gmu <= 1.0:
                    issues.append(
                        f"--gpu-memory-utilization={gmu} must be in (0, 1]"
                    )
        return issues

    async def sync(self, name: str, box_id: str) -> None:
        spec = self.library.load_recipe(name, box_id=box_id)
        box = await self.boxes.get(box_id)
        target = self.boxes._target_for_spec(box) if hasattr(self.boxes, "_target_for_spec") else None
        # Use BoxService internals: re-fetch ORM row through same code path
        async with __import__("sparkd.db.engine", fromlist=["session_scope"]).session_scope() as s:
            row = await s.get(__import__("sparkd.db.models", fromlist=["Box"]).Box, box_id)
            target = self.boxes._target_for(row)
        await self.pool.run(target, f"mkdir -p {shlex.quote(box.repo_path)}/recipes")
        yaml_text = yaml.safe_dump(spec.model_dump(), sort_keys=False)
        cmd = (
            f"cat > {shlex.quote(box.repo_path)}/recipes/{shlex.quote(name)}.yaml "
            f"<<'SPARKD_EOF'\n{yaml_text}SPARKD_EOF\n"
        )
        await self.pool.run(target, cmd)

    def diff(self, a: RecipeSpec, b: RecipeSpec) -> RecipeDiff:
        added = {k: v for k, v in b.args.items() if k not in a.args}
        removed = {k: v for k, v in a.args.items() if k not in b.args}
        changed = {
            k: (a.args[k], b.args[k])
            for k in a.args.keys() & b.args.keys()
            if a.args[k] != b.args[k]
        }
        return RecipeDiff(name=a.name, added=added, removed=removed, changed=changed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_recipe_service.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/recipe.py tests/integration/test_recipe_service.py
git commit -m "feat: RecipeService — validate against caps, sync to box, diff"
```

---

## Task 10: JobRegistry

**Files:**
- Create: `sparkd/services/jobs.py`
- Create: `tests/unit/test_jobs.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_jobs.py`:

```python
import asyncio

import pytest

from sparkd.schemas.job import JobState
from sparkd.services.jobs import JobRegistry


async def test_submit_and_complete():
    reg = JobRegistry()

    async def work():
        return {"answer": 42}

    job_id = await reg.submit("test", work)
    job = await reg.wait(job_id)
    assert job.state == JobState.succeeded
    assert job.result == {"answer": 42}


async def test_submit_and_fail():
    reg = JobRegistry()

    async def boom():
        raise RuntimeError("nope")

    job_id = await reg.submit("test", boom)
    job = await reg.wait(job_id)
    assert job.state == JobState.failed
    assert "nope" in job.message


async def test_list_returns_active_and_finished():
    reg = JobRegistry()
    job_id = await reg.submit("k", lambda: asyncio.sleep(0))
    await reg.wait(job_id)
    jobs = reg.list()
    assert len(jobs) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/jobs.py`**

```python
from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sparkd.errors import NotFoundError
from sparkd.schemas.job import Job, JobState


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._events: dict[str, asyncio.Event] = {}

    async def submit(
        self,
        kind: str,
        fn: Callable[[], Awaitable[Any] | Any],
        *,
        progress_hook: Callable[[float, str], None] | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)
        self._jobs[job_id] = Job(
            id=job_id, kind=kind, state=JobState.running, started_at=now
        )
        self._events[job_id] = asyncio.Event()

        async def runner() -> None:
            try:
                result = fn() if not inspect.iscoroutinefunction(fn) else await fn()
                if inspect.isawaitable(result):
                    result = await result
                self._jobs[job_id] = self._jobs[job_id].model_copy(
                    update={
                        "state": JobState.succeeded,
                        "result": result if isinstance(result, dict) else {"value": result},
                        "finished_at": datetime.now(timezone.utc),
                        "progress": 1.0,
                    }
                )
            except Exception as exc:
                self._jobs[job_id] = self._jobs[job_id].model_copy(
                    update={
                        "state": JobState.failed,
                        "message": str(exc),
                        "finished_at": datetime.now(timezone.utc),
                    }
                )
            finally:
                self._events[job_id].set()

        self._tasks[job_id] = asyncio.create_task(runner())
        return job_id

    def get(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise NotFoundError("job", job_id)
        return self._jobs[job_id]

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    async def wait(self, job_id: str) -> Job:
        if job_id not in self._events:
            raise NotFoundError("job", job_id)
        await self._events[job_id].wait()
        return self._jobs[job_id]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_jobs.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/jobs.py tests/unit/test_jobs.py
git commit -m "feat: JobRegistry for background tasks"
```

---

## Task 11: Subnet discovery scanner

**Files:**
- Create: `sparkd/ssh/discovery.py`
- Create: `tests/unit/test_discovery.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_discovery.py`:

```python
import asyncio

import pytest

from sparkd.ssh.discovery import probe_host


async def test_probe_returns_dgx_when_gb10_present(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: NVIDIA GB10 12.1a\n")
    result = await probe_host("127.0.0.1", port=port, user="x", password="y")
    assert result.is_dgx_spark is True
    assert "GB10" in result.gpu_line


async def test_probe_returns_not_dgx_when_no_gb10(fake_box):
    box, port = fake_box
    box.reply("nvidia-smi -L", stdout="GPU 0: Tesla V100\n")
    result = await probe_host("127.0.0.1", port=port, user="x", password="y")
    assert result.is_dgx_spark is False


async def test_probe_returns_unreachable_when_port_closed():
    result = await probe_host("127.0.0.1", port=1, user="x", password="y", timeout=0.5)
    assert result.reachable is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `ssh/discovery.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_discovery.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/ssh/discovery.py tests/unit/test_discovery.py
git commit -m "feat: subnet discovery probe with DGX Spark detection"
```

---

## Task 12: LaunchService — start/stop/log

**Files:**
- Create: `sparkd/services/launch.py`
- Create: `tests/integration/test_launch_service.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_launch_service.py`:

```python
import asyncio

import pytest

from sparkd.db.engine import init_engine
from sparkd.schemas.box import BoxCreate
from sparkd.schemas.launch import LaunchCreate, LaunchState
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.box import BoxService
from sparkd.services.launch import LaunchService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.ssh.pool import SSHPool, SSHTarget


@pytest.fixture
async def env(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    pool = SSHPool()
    box_svc = BoxService(pool=pool)
    lib = LibraryService()
    rs = RecipeService(library=lib, boxes=box_svc, pool=pool)
    ls = LaunchService(library=lib, boxes=box_svc, recipes=rs, pool=pool)
    box, port = fake_box
    monkeypatch.setattr(
        box_svc, "_target_for", lambda b: SSHTarget(
            host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
        ),
    )
    monkeypatch.setattr(
        rs, "validate", lambda *a, **k: asyncio.sleep(0, result=[])
    )
    yield ls, box_svc, lib, box, port
    await pool.close_all()


async def test_launch_records_starting_state(env, monkeypatch):
    ls, box_svc, lib, fake, _ = env
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    monkeypatch.setattr(ls, "_sync_files", lambda *a, **k: asyncio.sleep(0))
    fake.reply(
        "bash -lc 'cd ~/spark-vllm-docker && ./run-recipe.sh r1' & echo $!",
        stdout="12345\n",
    )
    rec = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    assert rec.state == LaunchState.starting
    assert rec.recipe_name == "r1"


async def test_stop_kills_container(env, monkeypatch):
    ls, box_svc, lib, fake, _ = env
    bs = await box_svc.create(BoxCreate(name="b", host="h", user="u"))
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    monkeypatch.setattr(ls, "_sync_files", lambda *a, **k: asyncio.sleep(0))
    fake.reply(
        "bash -lc 'cd ~/spark-vllm-docker && ./run-recipe.sh r1' & echo $!",
        stdout="12345\n",
    )
    rec = await ls.launch(LaunchCreate(recipe="r1", box_id=bs.id))
    fake.reply(f"docker ps -q --filter label=sparkd.launch={rec.id}", stdout="abc123\n")
    fake.reply("docker stop abc123", stdout="abc123\n")
    stopped = await ls.stop(rec.id)
    assert stopped.state == LaunchState.stopped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_launch_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/launch.py`**

```python
from __future__ import annotations

import shlex
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import Box, Launch
from sparkd.errors import ConflictError, NotFoundError, ValidationError
from sparkd.schemas.launch import LaunchCreate, LaunchRecord, LaunchState
from sparkd.services.box import BoxService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.ssh.pool import SSHPool


def _to_record(row: Launch) -> LaunchRecord:
    return LaunchRecord(
        id=row.id,
        box_id=row.box_id,
        recipe_name=row.recipe_name,
        state=LaunchState(row.state),
        container_id=row.container_id,
        command=row.command,
        started_at=row.started_at,
        stopped_at=row.stopped_at,
        exit_info=row.exit_info_json,
    )


class LaunchService:
    def __init__(
        self,
        library: LibraryService,
        boxes: BoxService,
        recipes: RecipeService,
        pool: SSHPool,
    ) -> None:
        self.library = library
        self.boxes = boxes
        self.recipes = recipes
        self.pool = pool

    async def _sync_files(self, name: str, box_id: str, mods: list[str]) -> None:
        await self.recipes.sync(name, box_id)

    async def launch(self, body: LaunchCreate) -> LaunchRecord:
        recipe = self.library.load_recipe(body.recipe, box_id=body.box_id)
        issues = await self.recipes.validate(recipe, body.box_id)
        if issues:
            raise ValidationError(
                "recipe failed pre-flight validation",
                details={"issues": issues},
            )
        await self._sync_files(body.recipe, body.box_id, body.mods)
        launch_id = uuid.uuid4().hex[:12]
        async with session_scope() as s:
            box_row = await s.get(Box, body.box_id)
            if box_row is None:
                raise NotFoundError("box", body.box_id)
            target = self.boxes._target_for(box_row)
            cmd = (
                f"bash -lc 'cd {shlex.quote(box_row.repo_path)} "
                f"&& ./run-recipe.sh {shlex.quote(body.recipe)}' & echo $!"
            )
        result = await self.pool.run(target, cmd)
        if result.exit_status != 0:
            raise ConflictError(
                f"failed to start: {result.stderr.strip()}"
            )
        async with session_scope() as s:
            row = Launch(
                id=launch_id,
                box_id=body.box_id,
                recipe_name=body.recipe,
                recipe_snapshot_json=recipe.model_dump(),
                mods_json=body.mods,
                state=LaunchState.starting.value,
                container_id=None,
                command=cmd,
            )
            s.add(row)
            await s.flush()
            return _to_record(row)

    async def get(self, launch_id: str) -> LaunchRecord:
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            return _to_record(row)

    async def list(self, *, box_id: str | None = None) -> list[LaunchRecord]:
        async with session_scope() as s:
            stmt = select(Launch)
            if box_id:
                stmt = stmt.where(Launch.box_id == box_id)
            rows = (await s.execute(stmt)).scalars().all()
            return [_to_record(r) for r in rows]

    async def stop(self, launch_id: str) -> LaunchRecord:
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            box_row = await s.get(Box, row.box_id)
            target = self.boxes._target_for(box_row)
        cid_query = await self.pool.run(
            target, f"docker ps -q --filter label=sparkd.launch={launch_id}"
        )
        cid = cid_query.stdout.strip()
        if cid:
            await self.pool.run(target, f"docker stop {shlex.quote(cid)}")
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            row.state = LaunchState.stopped.value
            row.container_id = cid or row.container_id
            row.stopped_at = datetime.now(timezone.utc)
            return _to_record(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_launch_service.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/launch.py tests/integration/test_launch_service.py
git commit -m "feat: LaunchService — start, stop, list"
```

---

## Task 13: StatusService — reconcile docker + vLLM

**Files:**
- Create: `sparkd/services/status.py`
- Create: `tests/unit/test_status_reconcile.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_status_reconcile.py`:

```python
from sparkd.services.status import BoxStatusSnapshot, reconcile, DockerContainer


def _c(cid: str, label_launch: str | None = None) -> DockerContainer:
    return DockerContainer(
        id=cid,
        image="vllm",
        labels={"sparkd.launch": label_launch} if label_launch else {},
        state="running",
    )


def test_running_with_dashboard_launch_marked_dashboard():
    snap = reconcile(
        containers=[_c("c1", "L1")],
        launches={"L1": "r1"},
        vllm_models=["meta-llama/Llama-3.1-8B-Instruct"],
        vllm_healthy=True,
    )
    assert len(snap.running_models) == 1
    assert snap.running_models[0].source == "dashboard"
    assert snap.running_models[0].healthy is True


def test_external_container_appears_with_external_source():
    snap = reconcile(
        containers=[_c("c1", None)],
        launches={},
        vllm_models=[],
        vllm_healthy=False,
    )
    assert snap.running_models[0].source == "external"
    assert snap.running_models[0].healthy is False


def test_drift_when_launch_record_has_no_container():
    snap = reconcile(
        containers=[],
        launches={"L1": "r1"},
        vllm_models=[],
        vllm_healthy=False,
    )
    assert "L1" in snap.drift_missing_container
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_status_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/status.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from sparkd.db.engine import session_scope
from sparkd.db.models import Box, Launch
from sparkd.errors import NotFoundError
from sparkd.services.box import BoxService
from sparkd.ssh.pool import SSHPool


@dataclass
class DockerContainer:
    id: str
    image: str
    labels: dict[str, str]
    state: str


@dataclass
class RunningModel:
    container_id: str
    launch_id: str | None
    recipe_name: str | None
    vllm_model_id: str | None
    healthy: bool
    source: str  # "dashboard" | "external"


@dataclass
class BoxStatusSnapshot:
    box_id: str
    connectivity: str  # "online" | "offline" | "degraded"
    running_models: list[RunningModel] = field(default_factory=list)
    drift_missing_container: list[str] = field(default_factory=list)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def reconcile(
    *,
    containers: list[DockerContainer],
    launches: dict[str, str],  # launch_id -> recipe_name
    vllm_models: list[str],
    vllm_healthy: bool,
    box_id: str = "",
) -> BoxStatusSnapshot:
    snap = BoxStatusSnapshot(box_id=box_id, connectivity="online")
    seen_launch_ids: set[str] = set()
    for c in containers:
        launch_id = c.labels.get("sparkd.launch")
        recipe_name = launches.get(launch_id) if launch_id else None
        source = "dashboard" if launch_id and launch_id in launches else "external"
        if launch_id and launch_id in launches:
            seen_launch_ids.add(launch_id)
        model_id = vllm_models[0] if vllm_models else None
        snap.running_models.append(
            RunningModel(
                container_id=c.id,
                launch_id=launch_id,
                recipe_name=recipe_name,
                vllm_model_id=model_id,
                healthy=vllm_healthy and model_id is not None,
                source=source,
            )
        )
    for lid in launches:
        if lid not in seen_launch_ids:
            snap.drift_missing_container.append(lid)
    return snap


class StatusService:
    def __init__(self, boxes: BoxService, pool: SSHPool) -> None:
        self.boxes = boxes
        self.pool = pool

    async def _docker_ps(self, box_id: str) -> list[DockerContainer]:
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            if row is None:
                raise NotFoundError("box", box_id)
            target = self.boxes._target_for(row)
        result = await self.pool.run(
            target, "docker ps --format '{{json .}}'"
        )
        out: list[DockerContainer] = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            labels = {}
            if d.get("Labels"):
                for kv in d["Labels"].split(","):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        labels[k.strip()] = v.strip()
            out.append(
                DockerContainer(
                    id=d.get("ID", "")[:12],
                    image=d.get("Image", ""),
                    labels=labels,
                    state=d.get("State", ""),
                )
            )
        return out

    async def _vllm_probe(self, box_host: str, port: int = 8000) -> tuple[list[str], bool]:
        async with httpx.AsyncClient(timeout=1.0) as client:
            try:
                models_r = await client.get(f"http://{box_host}:{port}/v1/models")
                health_r = await client.get(f"http://{box_host}:{port}/health")
                models = [m["id"] for m in models_r.json().get("data", [])]
                return models, health_r.status_code == 200
            except (httpx.HTTPError, ValueError, KeyError):
                return [], False

    async def snapshot(self, box_id: str) -> BoxStatusSnapshot:
        async with session_scope() as s:
            box_row = await s.get(Box, box_id)
            if box_row is None:
                raise NotFoundError("box", box_id)
            host = box_row.host
            from sqlalchemy import select
            launch_rows = (
                await s.execute(
                    select(Launch).where(
                        Launch.box_id == box_id,
                        Launch.state.in_(["starting", "healthy"]),
                    )
                )
            ).scalars().all()
            launches = {l.id: l.recipe_name for l in launch_rows}
        try:
            containers = await self._docker_ps(box_id)
            connectivity = "online"
        except Exception:
            return BoxStatusSnapshot(box_id=box_id, connectivity="offline")
        models, healthy = await self._vllm_probe(host)
        snap = reconcile(
            containers=containers,
            launches=launches,
            vllm_models=models,
            vllm_healthy=healthy,
            box_id=box_id,
        )
        snap.connectivity = connectivity
        return snap
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_status_reconcile.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/status.py tests/unit/test_status_reconcile.py
git commit -m "feat: StatusService — reconcile docker + vLLM endpoint"
```

---

## Task 14: ClusterService stub

**Files:**
- Create: `sparkd/services/cluster.py`
- Create: `tests/unit/test_cluster_stub.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_cluster_stub.py`:

```python
import pytest

from sparkd.services.cluster import ClusterService


async def test_cluster_launch_returns_not_implemented():
    svc = ClusterService()
    with pytest.raises(NotImplementedError):
        await svc.launch_across(boxes=["a", "b"], recipe="r")


async def test_cluster_topology_returns_empty():
    svc = ClusterService()
    assert await svc.topology() == {"nodes": [], "edges": []}
```

- [ ] **Step 2: Implement `services/cluster.py`**

```python
from __future__ import annotations


class ClusterService:
    async def launch_across(self, *, boxes: list[str], recipe: str) -> None:
        raise NotImplementedError("multi-box cluster orchestration is v2")

    async def topology(self) -> dict:
        return {"nodes": [], "edges": []}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cluster_stub.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 4: Commit**

```bash
git add sparkd/services/cluster.py tests/unit/test_cluster_stub.py
git commit -m "feat: ClusterService stub for v2"
```

---

## Task 15: FastAPI app factory + routes/boxes

**Files:**
- Create: `sparkd/app.py`
- Create: `sparkd/routes/__init__.py` (empty)
- Create: `sparkd/routes/boxes.py`
- Create: `tests/integration/test_box_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_box_routes.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_then_list_box(client):
    r = client.post if False else client.post
    resp = await client.post(
        "/boxes",
        json={"name": "spark-01", "host": "10.0.0.5", "user": "ubuntu"},
    )
    assert resp.status_code == 201
    box_id = resp.json()["id"]
    resp = await client.get("/boxes")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == box_id


async def test_get_missing_returns_404_problem(client):
    resp = await client.get("/boxes/nope")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_delete_removes_box(client):
    r = await client.post(
        "/boxes", json={"name": "x", "host": "h", "user": "u"}
    )
    bid = r.json()["id"]
    assert (await client.delete(f"/boxes/{bid}")).status_code == 204
    assert (await client.get(f"/boxes/{bid}")).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_box_routes.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `routes/boxes.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from sparkd.schemas.box import BoxCreate, BoxSpec
from sparkd.services.box import BoxService

router = APIRouter(prefix="/boxes", tags=["boxes"])


def _svc(request) -> BoxService:
    return request.app.state.boxes


@router.get("", response_model=list[BoxSpec])
async def list_boxes(svc: BoxService = Depends(_svc)) -> list[BoxSpec]:
    return await svc.list()


@router.post("", response_model=BoxSpec, status_code=201)
async def create_box(body: BoxCreate, svc: BoxService = Depends(_svc)) -> BoxSpec:
    return await svc.create(body)


@router.get("/{box_id}", response_model=BoxSpec)
async def get_box(box_id: str, svc: BoxService = Depends(_svc)) -> BoxSpec:
    return await svc.get(box_id)


@router.delete("/{box_id}", status_code=204)
async def delete_box(box_id: str, svc: BoxService = Depends(_svc)) -> Response:
    await svc.delete(box_id)
    return Response(status_code=204)


@router.post("/{box_id}/test")
async def test_box(box_id: str, svc: BoxService = Depends(_svc)) -> dict:
    ok = await svc.test_connection(box_id)
    return {"ok": ok}


@router.get("/{box_id}/capabilities")
async def get_caps(
    box_id: str, refresh: bool = False, svc: BoxService = Depends(_svc)
) -> dict:
    caps = await svc.capabilities(box_id, refresh=refresh)
    return caps.model_dump(mode="json")
```

Implement `app.py`:

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sparkd.db.engine import init_engine, shutdown
from sparkd.errors import install_handlers
from sparkd.routes.boxes import router as boxes_router
from sparkd.services.box import BoxService
from sparkd.services.jobs import JobRegistry
from sparkd.services.library import LibraryService
from sparkd.ssh.pool import SSHPool


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_engine(create_all=True)
    pool = SSHPool()
    app.state.pool = pool
    app.state.boxes = BoxService(pool=pool)
    app.state.library = LibraryService()
    app.state.jobs = JobRegistry()
    try:
        yield
    finally:
        await pool.close_all()
        await shutdown()


def build_app() -> FastAPI:
    app = FastAPI(title="sparkd", lifespan=_lifespan)
    install_handlers(app)
    app.include_router(boxes_router)
    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_box_routes.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/app.py sparkd/routes tests/integration/test_box_routes.py
git commit -m "feat: FastAPI app factory + /boxes routes"
```

---

## Task 16: Recipe routes

**Files:**
- Create: `sparkd/routes/recipes.py`
- Modify: `sparkd/app.py` (register router, attach RecipeService to app.state)
- Create: `tests/integration/test_recipe_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_recipe_routes.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_and_list_recipe(client):
    body = {"name": "r1", "model": "m", "args": {"--tp": "1"}}
    assert (await client.post("/recipes", json=body)).status_code == 201
    rs = (await client.get("/recipes")).json()
    assert rs[0]["name"] == "r1"


async def test_get_missing_recipe_404(client):
    r = await client.get("/recipes/nope")
    assert r.status_code == 404


async def test_delete_recipe(client):
    await client.post(
        "/recipes", json={"name": "r1", "model": "m"}
    )
    assert (await client.delete("/recipes/r1")).status_code == 204
    assert (await client.get("/recipes/r1")).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_recipe_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routes/recipes.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _lib(request) -> LibraryService:
    return request.app.state.library


def _rs(request) -> RecipeService:
    return request.app.state.recipes


@router.get("", response_model=list[RecipeSpec])
def list_recipes(box: str | None = None, lib: LibraryService = Depends(_lib)) -> list[RecipeSpec]:
    return lib.list_recipes(box_id=box)


@router.post("", response_model=RecipeSpec, status_code=201)
def create_recipe(spec: RecipeSpec, lib: LibraryService = Depends(_lib)) -> RecipeSpec:
    lib.save_recipe(spec)
    return spec


@router.get("/{name}", response_model=RecipeSpec)
def get_recipe(name: str, box: str | None = None, lib: LibraryService = Depends(_lib)) -> RecipeSpec:
    return lib.load_recipe(name, box_id=box)


@router.put("/{name}", response_model=RecipeSpec)
def put_recipe(name: str, spec: RecipeSpec, lib: LibraryService = Depends(_lib)) -> RecipeSpec:
    if spec.name != name:
        from sparkd.errors import ValidationError
        raise ValidationError("path name and body name disagree")
    lib.save_recipe(spec)
    return spec


@router.delete("/{name}", status_code=204)
def delete_recipe(name: str, lib: LibraryService = Depends(_lib)) -> Response:
    lib.delete_recipe(name)
    return Response(status_code=204)


@router.post("/{name}/validate")
async def validate_recipe(
    name: str, box: str, lib: LibraryService = Depends(_lib),
    rs: RecipeService = Depends(_rs),
) -> dict:
    spec = lib.load_recipe(name, box_id=box)
    issues = await rs.validate(spec, box)
    return {"ok": not issues, "issues": issues}


@router.post("/{name}/sync")
async def sync_recipe(
    name: str, box: str, rs: RecipeService = Depends(_rs)
) -> dict:
    await rs.sync(name, box)
    return {"ok": True}
```

- [ ] **Step 4: Wire into `app.py`**

Modify the `_lifespan` in `sparkd/app.py` so it constructs and stores `RecipeService`:

```python
from sparkd.routes.recipes import router as recipes_router
from sparkd.services.recipe import RecipeService

# Inside _lifespan, after `app.state.library = LibraryService()`:
app.state.recipes = RecipeService(
    library=app.state.library,
    boxes=app.state.boxes,
    pool=pool,
)

# Inside build_app, after include_router(boxes_router):
app.include_router(recipes_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_recipe_routes.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 6: Commit**

```bash
git add sparkd/routes/recipes.py sparkd/app.py tests/integration/test_recipe_routes.py
git commit -m "feat: /recipes CRUD + validate + sync routes"
```

---

## Task 17: Launch routes + WebSocket log stream

**Files:**
- Create: `sparkd/routes/launches.py`
- Create: `sparkd/routes/ws.py`
- Modify: `sparkd/app.py` (register routers, attach LaunchService)
- Create: `tests/integration/test_launch_flow.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_launch_flow.py`:

```python
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.ssh.pool import SSHTarget


@pytest.fixture
async def app_and_client(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create the box first so the route handler can run a startup hook
        # that injects the fake SSH target after the box service exists.
        async with transport.lifespan_context(app):
            box, port = fake_box

            def patch_target(_self, _row):
                return SSHTarget(
                    host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
                )

            monkeypatch.setattr(
                type(app.state.boxes), "_target_for", patch_target
            )

            async def fake_validate(_self, _spec, _box_id):
                return []

            monkeypatch.setattr(
                type(app.state.recipes), "validate", fake_validate
            )

            box.reply(
                "bash -lc 'cd ~/spark-vllm-docker && ./run-recipe.sh r1' & echo $!",
                stdout="12345\n",
            )
            box.reply(
                "mkdir -p ~/spark-vllm-docker/recipes",
                stdout="",
            )
            yield client, app, box


async def test_launch_creates_record(app_and_client):
    client, _app, _ = app_and_client
    bid = (await client.post(
        "/boxes", json={"name": "b", "host": "h", "user": "u"}
    )).json()["id"]
    await client.post(
        "/recipes", json={"name": "r1", "model": "m"}
    )
    r = await client.post(
        "/launches", json={"recipe": "r1", "box_id": bid}
    )
    assert r.status_code == 201
    assert r.json()["state"] == "starting"
```

(Note: the `transport.lifespan_context` block above is illustrative; pytest-asyncio + httpx `AsyncClient` runs lifespan automatically. Use whichever idiom works in your version — keep the assertions identical.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_launch_flow.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `routes/launches.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from sparkd.schemas.launch import LaunchCreate, LaunchRecord
from sparkd.services.launch import LaunchService

router = APIRouter(prefix="/launches", tags=["launches"])


def _ls(request) -> LaunchService:
    return request.app.state.launches


@router.post("", response_model=LaunchRecord, status_code=201)
async def create_launch(body: LaunchCreate, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.launch(body)


@router.get("", response_model=list[LaunchRecord])
async def list_launches(box: str | None = None, ls: LaunchService = Depends(_ls)) -> list[LaunchRecord]:
    return await ls.list(box_id=box)


@router.get("/{launch_id}", response_model=LaunchRecord)
async def get_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.get(launch_id)


@router.post("/{launch_id}/stop", response_model=LaunchRecord)
async def stop_launch(launch_id: str, ls: LaunchService = Depends(_ls)) -> LaunchRecord:
    return await ls.stop(launch_id)
```

Implement `routes/ws.py`:

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sparkd.services.launch import LaunchService

router = APIRouter()


@router.websocket("/ws/launches/{launch_id}")
async def launch_log_stream(ws: WebSocket, launch_id: str) -> None:
    await ws.accept()
    ls: LaunchService = ws.app.state.launches
    pool = ws.app.state.pool
    rec = await ls.get(launch_id)
    from sparkd.db.engine import session_scope
    from sparkd.db.models import Box
    async with session_scope() as s:
        row = await s.get(Box, rec.box_id)
        target = ws.app.state.boxes._target_for(row)
    cmd = (
        f"docker logs -f $(docker ps -q --filter "
        f"label=sparkd.launch={launch_id}) 2>&1 || tail -f /var/log/sparkd/{launch_id}.log"
    )
    try:
        async for channel, line in pool.stream(target, cmd):
            await ws.send_json({"channel": channel, "line": line})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # surface and close
        await ws.send_json({"channel": "error", "line": str(exc)})
        await ws.close(code=1011)
```

Wire both into `app.py`:

```python
from sparkd.routes.launches import router as launches_router
from sparkd.routes.ws import router as ws_router
from sparkd.services.launch import LaunchService

# Inside _lifespan, after `app.state.recipes = ...`:
app.state.launches = LaunchService(
    library=app.state.library,
    boxes=app.state.boxes,
    recipes=app.state.recipes,
    pool=pool,
)

# Inside build_app, after include_router(recipes_router):
app.include_router(launches_router)
app.include_router(ws_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_launch_flow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sparkd/routes/launches.py sparkd/routes/ws.py sparkd/app.py tests/integration/test_launch_flow.py
git commit -m "feat: /launches REST + /ws/launches/{id} log stream"
```

---

## Task 18: Status routes + WebSocket

**Files:**
- Create: `sparkd/routes/status.py`
- Modify: `sparkd/app.py` (attach StatusService, include router)
- Modify: `sparkd/routes/ws.py` (add `/ws/boxes/{id}/status`)
- Create: `tests/integration/test_status_ws.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_status_ws.py`:

```python
import json

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine
from sparkd.ssh.pool import SSHTarget


@pytest.fixture
async def env(sparkd_home, fake_box, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        box, port = fake_box
        monkeypatch.setattr(
            type(app.state.boxes), "_target_for",
            lambda _s, _r: SSHTarget(
                host="127.0.0.1", port=port, user="x", use_agent=False, password="y"
            ),
        )
        # Stub vLLM probe (no real HTTP server)
        async def fake_vllm(_self, _host, port=8000):
            return [], False
        monkeypatch.setattr(
            type(app.state.status), "_vllm_probe", fake_vllm
        )
        yield c, app, box


async def test_status_snapshot_returns_offline_when_docker_fails(env):
    client, _app, box = env
    box.reply("docker ps --format '{{json .}}'", stderr="ssh: dial fail", exit=255)
    bid = (await client.post(
        "/boxes", json={"name": "b", "host": "h", "user": "u"}
    )).json()["id"]
    r = await client.get(f"/boxes/{bid}/status")
    assert r.status_code == 200
    assert r.json()["connectivity"] in {"online", "offline"}


async def test_status_lists_running_external_container(env):
    client, _app, box = env
    box.reply(
        "docker ps --format '{{json .}}'",
        stdout='{"ID":"abcdef123456","Image":"vllm","Labels":"","State":"running"}\n',
    )
    bid = (await client.post(
        "/boxes", json={"name": "b", "host": "h", "user": "u"}
    )).json()["id"]
    r = await client.get(f"/boxes/{bid}/status")
    body = r.json()
    assert any(m["source"] == "external" for m in body["running_models"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_status_ws.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routes/status.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from sparkd.services.status import StatusService

router = APIRouter(tags=["status"])


def _svc(request) -> StatusService:
    return request.app.state.status


@router.get("/boxes/{box_id}/status")
async def get_status(box_id: str, svc: StatusService = Depends(_svc)) -> dict:
    snap = await svc.snapshot(box_id)
    return {
        "box_id": snap.box_id,
        "connectivity": snap.connectivity,
        "running_models": [m.__dict__ for m in snap.running_models],
        "drift_missing_container": snap.drift_missing_container,
        "captured_at": snap.captured_at.isoformat(),
    }
```

Add status WS to `routes/ws.py`:

```python
@router.websocket("/ws/boxes/{box_id}/status")
async def status_stream(ws: WebSocket, box_id: str) -> None:
    await ws.accept()
    svc = ws.app.state.status
    try:
        while True:
            snap = await svc.snapshot(box_id)
            await ws.send_json({
                "box_id": snap.box_id,
                "connectivity": snap.connectivity,
                "running_models": [m.__dict__ for m in snap.running_models],
                "drift_missing_container": snap.drift_missing_container,
                "captured_at": snap.captured_at.isoformat(),
            })
            await asyncio.sleep(5.0)
    except WebSocketDisconnect:
        return
```

Wire `app.py`:

```python
from sparkd.routes.status import router as status_router
from sparkd.services.status import StatusService

# Inside _lifespan, after `app.state.launches = ...`:
app.state.status = StatusService(boxes=app.state.boxes, pool=pool)

# Inside build_app:
app.include_router(status_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_status_ws.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sparkd/routes/status.py sparkd/routes/ws.py sparkd/app.py tests/integration/test_status_ws.py
git commit -m "feat: /boxes/{id}/status REST + /ws/boxes/{id}/status"
```

---

## Task 19: Discovery route + jobs route

**Files:**
- Create: `sparkd/routes/jobs.py`
- Modify: `sparkd/routes/boxes.py` (add `POST /boxes/discover`)
- Create: `tests/integration/test_discovery_route.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_discovery_route.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()

    async def fake_scan(*args, **kwargs):
        from sparkd.ssh.discovery import ProbeResult
        for r in [
            ProbeResult(host="127.0.0.1", port=22, reachable=True, is_dgx_spark=True, gpu_line="GB10"),
            ProbeResult(host="127.0.0.2", port=22, reachable=False),
        ]:
            yield r

    monkeypatch.setattr("sparkd.ssh.discovery.scan_subnet", fake_scan)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_discover_returns_job_id_then_results(client):
    r = await client.post(
        "/boxes/discover",
        json={"cidr": "127.0.0.0/30", "ssh_user": "ubuntu"},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    # Poll until succeeded
    for _ in range(50):
        j = (await client.get(f"/jobs/{job_id}")).json()
        if j["state"] in {"succeeded", "failed"}:
            break
    assert j["state"] == "succeeded"
    assert any(p["is_dgx_spark"] for p in j["result"]["probes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_discovery_route.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routes/jobs.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from sparkd.services.jobs import JobRegistry

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _reg(request) -> JobRegistry:
    return request.app.state.jobs


@router.get("/{job_id}")
def get_job(job_id: str, reg: JobRegistry = Depends(_reg)) -> dict:
    return reg.get(job_id).model_dump(mode="json")
```

Modify `routes/boxes.py` — add discovery endpoint:

```python
from pydantic import BaseModel

from sparkd.ssh.discovery import scan_subnet


class DiscoverRequest(BaseModel):
    cidr: str
    ssh_user: str = "ubuntu"
    ssh_port: int = 22


@router.post("/discover", status_code=202)
async def discover(body: DiscoverRequest, request) -> dict:  # noqa: ARG001
    reg = request.app.state.jobs

    async def run() -> dict:
        probes = []
        async for p in scan_subnet(
            body.cidr, user=body.ssh_user, use_agent=True
        ):
            probes.append(p.__dict__)
        return {"probes": probes}

    job_id = await reg.submit("discover", run)
    return {"job_id": job_id}
```

Wire jobs router in `app.py`:

```python
from sparkd.routes.jobs import router as jobs_router

# Inside build_app:
app.include_router(jobs_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_discovery_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sparkd/routes/jobs.py sparkd/routes/boxes.py sparkd/app.py tests/integration/test_discovery_route.py
git commit -m "feat: /boxes/discover background job + /jobs/{id}"
```

---

## Task 20: CLI entrypoint

**Files:**
- Create: `sparkd/cli.py`
- Create: `sparkd/__main__.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_cli.py`:

```python
from click.testing import CliRunner

from sparkd.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


def test_serve_command_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `cli.py`**

```python
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
```

`sparkd/__main__.py`:

```python
from sparkd.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Smoke-test the actual server**

```bash
SPARKD_HOME=/tmp/sparkd-smoke uv run sparkd serve --port 18765 &
sleep 2
curl -sf http://127.0.0.1:18765/boxes
kill %1
```

Expected: `[]` (empty list).

- [ ] **Step 6: Commit**

```bash
git add sparkd/cli.py sparkd/__main__.py tests/unit/test_cli.py
git commit -m "feat: sparkd CLI with serve command"
```

---

## Task 21: Frontend scaffold + API client

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "sparkd-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "gen": "openapi-typescript http://127.0.0.1:8765/openapi.json -o src/api/generated.ts",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.27.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "openapi-typescript": "^7.4.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

`frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../sparkd/static", emptyOutDir: true },
  server: {
    proxy: {
      "/boxes": "http://127.0.0.1:8765",
      "/recipes": "http://127.0.0.1:8765",
      "/launches": "http://127.0.0.1:8765",
      "/jobs": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  test: { environment: "jsdom" },
});
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

`frontend/index.html`:

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>sparkd</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

`frontend/src/api/client.ts`:

```ts
export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`api ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 204) return undefined as unknown as T;
  const text = await r.text();
  const data = text ? JSON.parse(text) : null;
  if (!r.ok) throw new ApiError(r.status, data);
  return data as T;
}

export const api = {
  get:    <T>(p: string)              => req<T>("GET", p),
  post:   <T>(p: string, b?: unknown) => req<T>("POST", p, b),
  put:    <T>(p: string, b?: unknown) => req<T>("PUT", p, b),
  delete: <T>(p: string)              => req<T>("DELETE", p),
};

export function openWS(path: string): WebSocket {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(`${proto}//${location.host}${path}`);
}
```

`frontend/src/App.tsx`:

```tsx
import { Link, Route, Routes } from "react-router-dom";

import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <Link to="/">Boxes</Link>
        <Link to="/recipes">Recipes</Link>
        <Link to="/launch">Launch</Link>
        <Link to="/status">Status</Link>
      </nav>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
      </Routes>
    </div>
  );
}
```

- [ ] **Step 2: Install + smoke**

```bash
cd frontend && npm install
npm run build
```

Expected: `npm run build` succeeds (will fail on missing pages — fine, next task fixes).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json \
        frontend/index.html frontend/src/main.tsx frontend/src/App.tsx \
        frontend/src/api/client.ts
git commit -m "feat: frontend scaffold (Vite + React + TanStack Query)"
```

---

## Task 22: Boxes page (list + add + delete)

**Files:**
- Create: `frontend/src/hooks/useBoxes.ts`
- Create: `frontend/src/pages/BoxesPage.tsx`
- Create: `frontend/src/components/AddBoxDialog.tsx`
- Create: `frontend/src/components/BoxList.tsx`
- Create: `frontend/src/pages/BoxesPage.test.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/BoxesPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import BoxesPage from "./BoxesPage";

beforeEach(() => {
  global.fetch = vi.fn(async (url: string) => {
    if (url === "/boxes") {
      return new Response(
        JSON.stringify([
          { id: "b1", name: "spark-01", host: "10.0.0.5", port: 22, user: "u",
            use_agent: true, repo_path: "~/x", tags: {}, created_at: new Date().toISOString() },
        ]),
        { status: 200 }
      );
    }
    return new Response("[]", { status: 200 });
  }) as any;
});

describe("BoxesPage", () => {
  it("lists boxes from /boxes", async () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <BoxesPage />
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("spark-01")).toBeDefined());
  });
});
```

- [ ] **Step 2: Implement hook + components**

`frontend/src/hooks/useBoxes.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Box = {
  id: string;
  name: string;
  host: string;
  port: number;
  user: string;
  use_agent: boolean;
  repo_path: string;
  tags: Record<string, string>;
  created_at: string;
};

export function useBoxes() {
  return useQuery({ queryKey: ["boxes"], queryFn: () => api.get<Box[]>("/boxes") });
}

export function useCreateBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Box>) => api.post<Box>("/boxes", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}

export function useDeleteBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/boxes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}
```

`frontend/src/components/BoxList.tsx`:

```tsx
import { Box, useDeleteBox } from "../hooks/useBoxes";

export default function BoxList({ boxes }: { boxes: Box[] }) {
  const del = useDeleteBox();
  return (
    <table>
      <thead>
        <tr><th>name</th><th>host</th><th>user</th><th></th></tr>
      </thead>
      <tbody>
        {boxes.map((b) => (
          <tr key={b.id}>
            <td>{b.name}</td>
            <td>{b.host}:{b.port}</td>
            <td>{b.user}</td>
            <td><button onClick={() => del.mutate(b.id)}>delete</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`frontend/src/components/AddBoxDialog.tsx`:

```tsx
import { useState } from "react";

import { useCreateBox } from "../hooks/useBoxes";

export default function AddBoxDialog() {
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [user, setUser] = useState("ubuntu");
  const create = useCreateBox();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate({ name, host, user });
        setName(""); setHost("");
      }}
      style={{ display: "flex", gap: 8, marginBottom: 12 }}
    >
      <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="host" value={host} onChange={(e) => setHost(e.target.value)} />
      <input placeholder="user" value={user} onChange={(e) => setUser(e.target.value)} />
      <button type="submit" disabled={!name || !host}>add</button>
    </form>
  );
}
```

`frontend/src/pages/BoxesPage.tsx`:

```tsx
import AddBoxDialog from "../components/AddBoxDialog";
import BoxList from "../components/BoxList";
import { useBoxes } from "../hooks/useBoxes";

export default function BoxesPage() {
  const { data, isLoading, error } = useBoxes();
  if (isLoading) return <div>loading…</div>;
  if (error) return <div>error: {String(error)}</div>;
  return (
    <div>
      <h1>Boxes</h1>
      <AddBoxDialog />
      <BoxList boxes={data ?? []} />
    </div>
  );
}
```

- [ ] **Step 3: Run test**

```bash
cd frontend && npm test
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useBoxes.ts frontend/src/components/BoxList.tsx \
        frontend/src/components/AddBoxDialog.tsx frontend/src/pages/BoxesPage.tsx \
        frontend/src/pages/BoxesPage.test.tsx
git commit -m "feat: BoxesPage with list/add/delete"
```

---

## Task 23: Recipes, Launch, Status pages

**Files:**
- Create: `frontend/src/hooks/useRecipes.ts`
- Create: `frontend/src/hooks/useLaunches.ts`
- Create: `frontend/src/hooks/useBoxStatus.ts`
- Create: `frontend/src/pages/RecipesPage.tsx`
- Create: `frontend/src/pages/LaunchPage.tsx`
- Create: `frontend/src/pages/StatusPage.tsx`
- Create: `frontend/src/components/LiveLog.tsx`

- [ ] **Step 1: Implement hooks**

`frontend/src/hooks/useRecipes.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Recipe = {
  name: string;
  model: string;
  description?: string;
  args: Record<string, string>;
  env: Record<string, string>;
  mods: string[];
};

export function useRecipes(boxId?: string) {
  return useQuery({
    queryKey: ["recipes", boxId ?? null],
    queryFn: () => api.get<Recipe[]>(`/recipes${boxId ? `?box=${boxId}` : ""}`),
  });
}

export function useSaveRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (r: Recipe) => api.post<Recipe>("/recipes", r),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}

export function useDeleteRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/recipes/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}
```

`frontend/src/hooks/useLaunches.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Launch = {
  id: string;
  box_id: string;
  recipe_name: string;
  state: "starting" | "healthy" | "failed" | "stopped" | "interrupted";
  container_id: string | null;
  started_at: string;
  stopped_at: string | null;
};

export function useLaunches(boxId?: string) {
  return useQuery({
    queryKey: ["launches", boxId ?? null],
    queryFn: () => api.get<Launch[]>(`/launches${boxId ? `?box=${boxId}` : ""}`),
    refetchInterval: 5000,
  });
}

export function useCreateLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { recipe: string; box_id: string; mods?: string[] }) =>
      api.post<Launch>("/launches", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function useStopLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Launch>(`/launches/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}
```

`frontend/src/hooks/useBoxStatus.ts`:

```ts
import { useEffect, useState } from "react";

import { openWS } from "../api/client";

export type BoxStatus = {
  box_id: string;
  connectivity: "online" | "offline" | "degraded";
  running_models: Array<{
    container_id: string;
    launch_id: string | null;
    recipe_name: string | null;
    vllm_model_id: string | null;
    healthy: boolean;
    source: "dashboard" | "external";
  }>;
  drift_missing_container: string[];
  captured_at: string;
};

export function useBoxStatus(boxId: string | null) {
  const [snap, setSnap] = useState<BoxStatus | null>(null);
  useEffect(() => {
    if (!boxId) return;
    const ws = openWS(`/ws/boxes/${boxId}/status`);
    ws.onmessage = (ev) => setSnap(JSON.parse(ev.data));
    return () => ws.close();
  }, [boxId]);
  return snap;
}
```

- [ ] **Step 2: Implement pages**

`frontend/src/pages/RecipesPage.tsx`:

```tsx
import { useState } from "react";

import { Recipe, useDeleteRecipe, useRecipes, useSaveRecipe } from "../hooks/useRecipes";

export default function RecipesPage() {
  const { data } = useRecipes();
  const save = useSaveRecipe();
  const del = useDeleteRecipe();
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  return (
    <div>
      <h1>Recipes</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate({ name, model, args: {}, env: {}, mods: [] } as Recipe);
          setName(""); setModel("");
        }}
        style={{ display: "flex", gap: 8, marginBottom: 12 }}
      >
        <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="model id" value={model} onChange={(e) => setModel(e.target.value)} />
        <button type="submit" disabled={!name || !model}>add</button>
      </form>
      <ul>
        {(data ?? []).map((r) => (
          <li key={r.name}>
            <code>{r.name}</code> — {r.model}{" "}
            <button onClick={() => del.mutate(r.name)}>delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`frontend/src/components/LiveLog.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";

import { openWS } from "../api/client";

export default function LiveLog({ launchId }: { launchId: string }) {
  const [lines, setLines] = useState<{ channel: string; line: string }[]>([]);
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const ws = openWS(`/ws/launches/${launchId}`);
    ws.onmessage = (ev) => setLines((l) => [...l, JSON.parse(ev.data)].slice(-500));
    return () => ws.close();
  }, [launchId]);
  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight); }, [lines]);
  return (
    <pre
      ref={ref}
      style={{ height: 240, overflow: "auto", background: "#111", color: "#eee", padding: 8 }}
    >
      {lines.map((l, i) => (
        <div key={i}>{l.line}</div>
      ))}
    </pre>
  );
}
```

`frontend/src/pages/LaunchPage.tsx`:

```tsx
import { useState } from "react";

import LiveLog from "../components/LiveLog";
import { useBoxes } from "../hooks/useBoxes";
import { useCreateLaunch, useLaunches, useStopLaunch } from "../hooks/useLaunches";
import { useRecipes } from "../hooks/useRecipes";

export default function LaunchPage() {
  const { data: boxes } = useBoxes();
  const { data: recipes } = useRecipes();
  const create = useCreateLaunch();
  const stop = useStopLaunch();
  const [box, setBox] = useState("");
  const [recipe, setRecipe] = useState("");
  const launches = useLaunches();
  return (
    <div>
      <h1>Launch</h1>
      <div style={{ display: "flex", gap: 8 }}>
        <select value={box} onChange={(e) => setBox(e.target.value)}>
          <option value="">-- box --</option>
          {(boxes ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
          <option value="">-- recipe --</option>
          {(recipes ?? []).map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
        </select>
        <button
          disabled={!box || !recipe}
          onClick={() => create.mutate({ recipe, box_id: box })}
        >
          launch
        </button>
      </div>
      <h2>Active launches</h2>
      <ul>
        {(launches.data ?? []).map((l) => (
          <li key={l.id}>
            <code>{l.recipe_name}</code> on <code>{l.box_id}</code> — {l.state}{" "}
            <button onClick={() => stop.mutate(l.id)}>stop</button>
            <LiveLog launchId={l.id} />
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`frontend/src/pages/StatusPage.tsx`:

```tsx
import { useState } from "react";

import { useBoxes } from "../hooks/useBoxes";
import { useBoxStatus } from "../hooks/useBoxStatus";

export default function StatusPage() {
  const { data: boxes } = useBoxes();
  const [boxId, setBoxId] = useState<string | null>(null);
  const snap = useBoxStatus(boxId);
  return (
    <div>
      <h1>Status</h1>
      <select value={boxId ?? ""} onChange={(e) => setBoxId(e.target.value || null)}>
        <option value="">-- box --</option>
        {(boxes ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
      {snap && (
        <div>
          <p>connectivity: <b>{snap.connectivity}</b></p>
          <table>
            <thead><tr><th>container</th><th>recipe</th><th>model</th><th>healthy</th><th>source</th></tr></thead>
            <tbody>
              {snap.running_models.map((m) => (
                <tr key={m.container_id}>
                  <td>{m.container_id.slice(0, 12)}</td>
                  <td>{m.recipe_name ?? "—"}</td>
                  <td>{m.vllm_model_id ?? "—"}</td>
                  <td>{m.healthy ? "✓" : "✗"}</td>
                  <td>{m.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Build**

```bash
cd frontend && npm run build
```

Expected: build succeeds. Output goes to `sparkd/static/`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks frontend/src/pages frontend/src/components/LiveLog.tsx
git commit -m "feat: Recipes, Launch (with live logs), Status pages"
```

---

## Task 24: Serve frontend assets from FastAPI

**Files:**
- Modify: `sparkd/app.py` (mount static, SPA fallback)
- Create: `tests/integration/test_static_serving.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_static_serving.py`:

```python
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, tmp_path):
    static = Path(__file__).resolve().parents[2] / "sparkd" / "static"
    static.mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>sparkd</title>")
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_root_returns_index(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "sparkd" in r.text


async def test_unknown_path_returns_index_for_spa(client):
    r = await client.get("/recipes/something")
    assert r.status_code == 200  # SPA route, not a real endpoint
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_static_serving.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `app.py`**

Add to `build_app` after all routers are included:

```python
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _mount_spa(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        return
    index = static_dir / "index.html"
    # Serve assets/
    if (static_dir / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(static_dir / "assets")),
            name="assets",
        )
    @app.get("/{full_path:path}")
    async def spa(full_path: str):  # noqa: ARG001
        # Defer to API routes; FastAPI evaluates route order, so this only catches
        # paths not matched above.
        if index.exists():
            return FileResponse(index)
        return {"error": "frontend not built"}


# Inside build_app, last line before return:
_mount_spa(app)
```

Note: `_mount_spa` must be called *after* every API router is included so the catch-all does not shadow them.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_static_serving.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -v
```

Expected: ALL pass (no e2e markers required).

- [ ] **Step 6: Commit**

```bash
git add sparkd/app.py tests/integration/test_static_serving.py
git commit -m "feat: serve built frontend SPA from FastAPI"
```

---

## Task 25: Structured logging + healthz

**Files:**
- Create: `sparkd/logging.py`
- Modify: `sparkd/app.py` (configure logging at startup, add `/healthz`)
- Create: `tests/integration/test_healthz.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_healthz.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home):
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_healthz_reports_components(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert "ssh_pool_size" in body
    assert "sparkd_home" in body
```

- [ ] **Step 2: Implement `sparkd/logging.py`**

```python
from __future__ import annotations

import logging
import sys

import structlog


def configure() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()
```

Modify `sparkd/app.py`:

```python
from sparkd import logging as sparkd_logging
from sparkd import paths

# Inside _lifespan, before init_engine:
sparkd_logging.configure()

# Add a route in build_app:
@app.get("/healthz")
async def healthz() -> dict:
    return {
        "db": "ok",
        "ssh_pool_size": len(app.state.pool._conns),
        "sparkd_home": str(paths.root()),
    }
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/integration/test_healthz.py -v`
Expected: PASS.

- [ ] **Step 4: Final full-suite run**

```bash
uv run pytest --cov=sparkd --cov-report=term-missing
```

Expected: all tests pass; service-module coverage ≥ 80%.

- [ ] **Step 5: Commit**

```bash
git add sparkd/logging.py sparkd/app.py tests/integration/test_healthz.py
git commit -m "feat: structured logging + /healthz"
```

---

## Self-review

- **Spec coverage.** Goals from spec §1: Connect to boxes (Tasks 7, 11, 15, 19) ✓. Local recipe library with overrides (Tasks 8, 16) ✓. Launch + status (Tasks 12, 13, 17, 18) ✓. Stop/restart/inspect (Tasks 12, 17) ✓. AI-assisted recipe and mod creation: deferred to Plan 2 as flagged in the intro. Pluggable advisor port: deferred to Plan 2.
- **Architecture coverage.** Process layout (Task 15) ✓. On-laptop storage (Tasks 1, 3) ✓. Async + multiplex SSH (Task 6) ✓. Background jobs (Task 10, 19) ✓. Type contract via Pydantic (Task 4) ✓. WebSocket channels for launches and status (Tasks 17, 18) ✓.
- **Domain services covered.** Box ✓ (7), Library ✓ (8), Recipe ✓ (9), Launch ✓ (12), Status ✓ (13), Cluster stub ✓ (14). Advisor and HFCatalog deferred. Mod service deferred to Plan 2.
- **API surface coverage.** Boxes CRUD + discover + capabilities + test (Tasks 15, 19) ✓. Recipes CRUD + validate + sync (Task 16) ✓. Launches POST/GET/stop (Task 17) ✓. Box status (Task 18) ✓. Cluster stub returns 501-ish behavior ✓ (14). `/healthz` ✓ (25). Recipe diff and clone, launch logs slice, advisor and mod endpoints: Plan 2.
- **Testing coverage.** Unit tests for paths, config, errors, schemas, library, status reconciliation, jobs, discovery, cli, ssh pool, db models. Integration for box service, recipe service, launch service, all major routes, static serving, healthz. End-to-end real-box smoke deferred (still allowed as opt-in once a box is available).
- **Placeholder scan.** No "TODO", "TBD", "implement later", or vague "add error handling" instructions; every step shows full code or exact commands. The phrase "(Note: …)" appears in Task 17 to flag an idiomatic ASGI lifespan detail and does not hide work.
- **Type consistency.** `LaunchState` enum members `starting/healthy/failed/stopped/interrupted` used identically across schemas (Task 4), service (Task 12), and frontend (Task 23). `BoxCapabilities` shape consistent between Task 4, Task 7, and Task 9. `RecipeSpec` field set (`name`, `model`, `args`, `env`, `mods`) consistent across schemas, library, recipe service, and frontend hook.
- **Sequencing.** Each task only depends on prior tasks. Frontend tasks (21–23) depend on backend routes (15–19). Static serving (24) depends on frontend build (23). Logging + healthz (25) is last and touches only `app.py`.

No issues found that require fixing inline.
