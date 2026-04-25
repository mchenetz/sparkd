# sparkd AI Features Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-assisted recipe generation, recipe optimization, and mod authoring to sparkd. Plus full mod browse/apply (no AI), Hugging Face model metadata fetching, and the corresponding REST/WS routes and React UI.

**Architecture:** A pluggable `AdvisorPort` interface with an `AnthropicAdapter` shipped in v1. Advisor sessions persist in SQLite for prompt-cache continuity. `HFCatalogService` fetches and caches model facts from the Hugging Face Hub so the advisor reasons against grounded data. `ModService` mirrors the existing `LibraryService`/`RecipeService` pattern: filesystem-backed mod directories, validate, apply, and `propose_mod` via the same advisor port. Streaming endpoints push tokens to the React advisor pane over WebSocket.

**Tech Stack:** anthropic SDK, keyring (OS secret store), httpx (HF Hub), pydantic v2, SQLAlchemy 2 async, FastAPI WebSocket, React + TanStack Query.

**Reference spec:** `docs/superpowers/specs/2026-04-25-sparkd-dashboard-design.md` — AdvisorService, HFCatalogService, ModService sections.

**Builds on Plan 1:** `docs/superpowers/plans/2026-04-25-sparkd-foundation.md` — current HEAD `8b2696e` on `master`.

---

## File structure

New backend modules:

```
sparkd/
  secrets.py                    # OS keyring read/write helpers (Anthropic key)
  schemas/
    advisor.py                  # AdvisorMessage, RecipeDraft, ModDraft, AdvisorSession
    mod.py                      # ModSpec, ModDraft
    hf.py                       # HFModelInfo
  services/
    hf_catalog.py               # HFCatalogService (httpx + sqlite cache)
    advisor.py                  # AdvisorService + AdvisorPort interface
    mod.py                      # ModService (filesystem + validate)
  advisor/
    __init__.py
    anthropic_adapter.py        # AnthropicAdapter implementing AdvisorPort
    prompts.py                  # System prompt + structured output schema
  routes/
    advisor.py                  # POST/GET /advisor/sessions/*
    mods.py                     # /mods CRUD + /mods/{name}/validate
    hf.py                       # GET /hf/models, /hf/models/{id}
  db/
    migrations/versions/0002_advisor_sessions.py
tests/
  unit/
    test_hf_catalog.py
    test_advisor_prompt.py
    test_mod_service.py
    test_secrets.py
  integration/
    test_advisor_service.py     # uses fake AdvisorPort
    test_advisor_routes.py
    test_mod_routes.py
    test_hf_routes.py
```

Modified backend modules:

```
sparkd/app.py                   # wire HFCatalog, Mod, Advisor services + routers
sparkd/db/models.py             # AdvisorSession ORM model
sparkd/routes/ws.py             # add /ws/advisor/{session}
pyproject.toml                  # add `anthropic>=0.39`
```

New frontend modules:

```
frontend/src/
  hooks/
    useAdvisor.ts               # advisor session + streamed tokens
    useMods.ts
    useHF.ts
  components/
    AdvisorChat.tsx             # streamed chat UI
    RecipeDraftPane.tsx         # rendered RecipeDraft + accept button
    ModDraftPane.tsx
  pages/
    AdvisorPage.tsx             # entry: pick HF model → generate recipe
    OptimizePage.tsx            # entry: pick recipe + box → optimize
    ModsPage.tsx                # browse/author mods
```

Modified frontend modules:

```
frontend/src/App.tsx            # add nav links: Advisor, Optimize, Mods
frontend/src/pages/RecipesPage.tsx   # "Optimize" button on each recipe → /optimize?recipe=
```

Each backend file owns one responsibility. The `AdvisorPort` is a small abstract base (`generate_recipe`, `optimize_recipe`, `propose_mod`, `chat_followup`) with the Anthropic adapter as the only concrete implementation in v1. The advisor never calls `RecipeService` or writes to disk — it returns drafts; the routes commit accepted drafts via `LibraryService`.

---

## Task 0: Add anthropic dependency + secrets module

**Files:**
- Modify: `pyproject.toml`
- Create: `sparkd/secrets.py`
- Create: `tests/unit/test_secrets.py`

- [ ] **Step 1: Add anthropic to dependencies**

Edit `pyproject.toml`, add `"anthropic>=0.39",` to the `dependencies` list (right after `httpx>=0.27`):

```toml
  "httpx>=0.27",
  "anthropic>=0.39",
]
```

- [ ] **Step 2: Sync**

Run: `cd /Users/mchenetz/git/sparkd && uv sync --extra dev`
Expected: installs `anthropic` and its deps, no errors.

- [ ] **Step 3: Write failing test**

`tests/unit/test_secrets.py`:

```python
import pytest

from sparkd import secrets as sec


def test_set_then_get_secret(monkeypatch):
    store = {}
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_secrets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sparkd.secrets'`.

- [ ] **Step 5: Implement `sparkd/secrets.py`**

```python
from __future__ import annotations

import keyring

_SERVICE = "sparkd"


def _backend_set(service: str, key: str, value: str) -> None:
    keyring.set_password(service, key, value)


def _backend_get(service: str, key: str) -> str | None:
    return keyring.get_password(service, key)


def _backend_delete(service: str, key: str) -> None:
    try:
        keyring.delete_password(service, key)
    except keyring.errors.PasswordDeleteError:
        pass


def set_secret(key: str, value: str) -> None:
    _backend_set(_SERVICE, key, value)


def get_secret(key: str) -> str | None:
    return _backend_get(_SERVICE, key)


def delete_secret(key: str) -> None:
    _backend_delete(_SERVICE, key)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_secrets.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock sparkd/secrets.py tests/unit/test_secrets.py
git commit -m "feat: anthropic dependency + OS keyring secrets helper"
```

---

## Task 1: Pydantic schemas for HF, mod, advisor

**Files:**
- Create: `sparkd/schemas/hf.py`
- Create: `sparkd/schemas/mod.py`
- Create: `sparkd/schemas/advisor.py`
- Modify: `sparkd/schemas/__init__.py` (re-export new types)
- Create: `tests/unit/test_ai_schemas.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_ai_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from sparkd.schemas.advisor import (
    AdvisorMessage,
    AdvisorSession,
    ModDraft,
    RecipeDraft,
)
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.mod import ModSpec


def test_hf_model_info_required_fields():
    info = HFModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct",
        architecture="LlamaForCausalLM",
        parameters_b=8.0,
        context_length=131072,
        supported_dtypes=["bf16", "fp16"],
    )
    assert info.id == "meta-llama/Llama-3.1-8B-Instruct"
    assert info.parameters_b == 8.0


def test_mod_spec_round_trip():
    m = ModSpec(name="patch-x", target_models=["llama"], description="d")
    d = m.model_dump()
    assert ModSpec(**d) == m


def test_recipe_draft_carries_rationale():
    d = RecipeDraft(
        name="r1", model="m",
        args={"--tp": "2"},
        env={},
        rationale="Two GPUs available; tp=2 fits.",
    )
    assert d.rationale.startswith("Two")


def test_mod_draft_has_files():
    d = ModDraft(
        name="m1",
        target_models=["llama"],
        files={"patch.diff": "...", "hook.sh": "#!/bin/sh\n"},
        rationale="r",
    )
    assert "patch.diff" in d.files


def test_advisor_message_roles():
    AdvisorMessage(role="user", content="hi")
    AdvisorMessage(role="assistant", content="hello")
    with pytest.raises(ValidationError):
        AdvisorMessage(role="bogus", content="x")


def test_advisor_session_minimum():
    s = AdvisorSession(id="s1", kind="recipe", target_box_id=None)
    assert s.kind == "recipe"
    assert s.messages == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_ai_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sparkd/schemas/hf.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HFModelInfo(BaseModel):
    id: str
    architecture: str = ""
    parameters_b: float = 0.0
    context_length: int = 0
    supported_dtypes: list[str] = Field(default_factory=list)
    license: str = ""
    pipeline_tag: str = ""
    fetched_at: datetime | None = None
```

- [ ] **Step 4: Implement `sparkd/schemas/mod.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ModSpec(BaseModel):
    name: str = Field(min_length=1)
    target_models: list[str] = Field(default_factory=list)
    description: str = ""
    files: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
```

- [ ] **Step 5: Implement `sparkd/schemas/advisor.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class RecipeDraft(BaseModel):
    name: str
    model: str
    args: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    rationale: str = ""


class ModDraft(BaseModel):
    name: str
    target_models: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    rationale: str = ""


class AdvisorSession(BaseModel):
    id: str
    kind: Literal["recipe", "optimize", "mod"]
    target_box_id: str | None = None
    target_recipe_name: str | None = None
    hf_model_id: str | None = None
    messages: list[AdvisorMessage] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime | None = None
```

- [ ] **Step 6: Update `sparkd/schemas/__init__.py`**

Append to the existing imports and `__all__`:

```python
from sparkd.schemas.advisor import (
    AdvisorMessage,
    AdvisorSession,
    ModDraft,
    RecipeDraft,
)
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.mod import ModSpec
```

Add to `__all__`:

```python
    "AdvisorMessage", "AdvisorSession", "ModDraft", "RecipeDraft",
    "HFModelInfo", "ModSpec",
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_ai_schemas.py -v`
Expected: PASS, 6 passed.

- [ ] **Step 8: Commit**

```bash
git add sparkd/schemas tests/unit/test_ai_schemas.py
git commit -m "feat: Pydantic schemas for HF model info, mod, advisor"
```

---

## Task 2: AdvisorSession DB table + alembic migration

**Files:**
- Modify: `sparkd/db/models.py`
- Create: `sparkd/db/migrations/versions/0002_advisor_sessions.py`
- Create: `tests/unit/test_advisor_session_model.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_advisor_session_model.py`:

```python
import pytest
from sqlalchemy import select

from sparkd.db.engine import init_engine, session_scope
from sparkd.db.models import AdvisorSessionRow


@pytest.fixture
async def db(sparkd_home):
    await init_engine(create_all=True)
    yield


async def test_insert_and_read_session(db):
    async with session_scope() as s:
        s.add(
            AdvisorSessionRow(
                id="s1",
                kind="recipe",
                target_box_id=None,
                hf_model_id="meta-llama/Llama-3.1-8B-Instruct",
                messages_json=[{"role": "user", "content": "hi"}],
                input_tokens=10,
                output_tokens=20,
            )
        )
    async with session_scope() as s:
        rows = (await s.execute(select(AdvisorSessionRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "recipe"
    assert rows[0].messages_json[0]["role"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_advisor_session_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'AdvisorSessionRow'`.

- [ ] **Step 3: Add `AdvisorSessionRow` to `sparkd/db/models.py`**

Append to the file (after `class AuditLog(Base): ...`):

```python
class AdvisorSessionRow(Base):
    __tablename__ = "advisor_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # recipe|optimize|mod
    target_box_id: Mapped[str | None] = mapped_column(String, nullable=True)
    target_recipe_name: Mapped[str | None] = mapped_column(String, nullable=True)
    hf_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    messages_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

Update `sparkd/db/__init__.py` to re-export:

```python
from sparkd.db.engine import init_engine, session_scope, shutdown
from sparkd.db.models import AdvisorSessionRow, AuditLog, Base, Box, Launch

__all__ = [
    "init_engine", "session_scope", "shutdown",
    "Base", "Box", "Launch", "AuditLog", "AdvisorSessionRow",
]
```

- [ ] **Step 4: Add alembic migration**

`sparkd/db/migrations/versions/0002_advisor_sessions.py`:

```python
"""advisor sessions

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advisor_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("target_box_id", sa.String(), nullable=True),
        sa.Column("target_recipe_name", sa.String(), nullable=True),
        sa.Column("hf_model_id", sa.String(), nullable=True),
        sa.Column("messages_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("advisor_sessions")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_advisor_session_model.py -v`
Expected: PASS, 1 passed.

- [ ] **Step 6: Commit**

```bash
git add sparkd/db tests/unit/test_advisor_session_model.py
git commit -m "feat: AdvisorSessionRow ORM table + 0002 migration"
```

---

## Task 3: HFCatalogService

**Files:**
- Create: `sparkd/services/hf_catalog.py`
- Create: `tests/unit/test_hf_catalog.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_hf_catalog.py`:

```python
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from sparkd.services.hf_catalog import HFCatalogService


@pytest.fixture
def svc(sparkd_home):
    return HFCatalogService()


@respx.mock
async def test_fetch_returns_parsed_info(svc):
    respx.get("https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "meta-llama/Llama-3.1-8B-Instruct",
                "pipeline_tag": "text-generation",
                "license": "llama3.1",
                "config": {
                    "architectures": ["LlamaForCausalLM"],
                    "max_position_embeddings": 131072,
                    "torch_dtype": "bfloat16",
                },
                "safetensors": {"total": 8030261248},
            },
        )
    )
    info = await svc.fetch("meta-llama/Llama-3.1-8B-Instruct")
    assert info.architecture == "LlamaForCausalLM"
    assert info.context_length == 131072
    assert "bf16" in info.supported_dtypes
    assert 7.5 < info.parameters_b < 8.5


@respx.mock
async def test_fetch_returns_cache_hit_within_ttl(svc, monkeypatch):
    route = respx.get(
        "https://huggingface.co/api/models/x/y"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "x/y", "config": {"architectures": ["A"]},
                "safetensors": {"total": 1_000_000_000},
            },
        )
    )
    a = await svc.fetch("x/y")
    b = await svc.fetch("x/y")
    assert a == b
    assert route.call_count == 1  # second call cached


@respx.mock
async def test_fetch_404_returns_minimal_info(svc):
    respx.get("https://huggingface.co/api/models/missing/x").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    info = await svc.fetch("missing/x")
    assert info.id == "missing/x"
    assert info.architecture == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_hf_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sparkd/services/hf_catalog.py`**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from sparkd.db.engine import session_scope
from sparkd.db.models import AuditLog
from sparkd.schemas.hf import HFModelInfo


_TTL = timedelta(hours=24)


def _normalize_dtype(t: str) -> str:
    s = (t or "").lower()
    if s in {"bfloat16", "bf16"}:
        return "bf16"
    if s in {"float16", "fp16", "half"}:
        return "fp16"
    if s in {"float32", "fp32"}:
        return "fp32"
    return s


class HFCatalogService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[datetime, HFModelInfo]] = {}

    async def fetch(self, model_id: str) -> HFModelInfo:
        now = datetime.now(timezone.utc)
        cached = self._cache.get(model_id)
        if cached and now - cached[0] < _TTL:
            return cached[1]
        info = await self._fetch_remote(model_id, now)
        self._cache[model_id] = (now, info)
        return info

    async def _fetch_remote(self, model_id: str, now: datetime) -> HFModelInfo:
        url = f"https://huggingface.co/api/models/{model_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.get(url)
            except httpx.HTTPError:
                return HFModelInfo(id=model_id, fetched_at=now)
        if r.status_code != 200:
            return HFModelInfo(id=model_id, fetched_at=now)
        body = r.json()
        config = body.get("config", {}) or {}
        archs = config.get("architectures") or []
        architecture = archs[0] if archs else ""
        ctx_len = int(
            config.get("max_position_embeddings")
            or config.get("max_seq_len")
            or 0
        )
        dtypes_raw = config.get("torch_dtype") or ""
        if isinstance(dtypes_raw, str) and dtypes_raw:
            dtypes = [_normalize_dtype(dtypes_raw)]
        else:
            dtypes = []
        # Approximate params from total bytes / 2 (bf16) → params; clamp to billions.
        params_b = 0.0
        ssft = body.get("safetensors") or {}
        total_bytes = int(ssft.get("total") or 0)
        if total_bytes:
            params_b = round(total_bytes / 2 / 1e9, 2)
        return HFModelInfo(
            id=model_id,
            architecture=architecture,
            parameters_b=params_b,
            context_length=ctx_len,
            supported_dtypes=dtypes,
            license=body.get("license", "") or "",
            pipeline_tag=body.get("pipeline_tag", "") or "",
            fetched_at=now,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_hf_catalog.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/hf_catalog.py tests/unit/test_hf_catalog.py
git commit -m "feat: HFCatalogService — fetch and cache HF model facts"
```

---

## Task 4: AdvisorPort interface + AnthropicAdapter

**Files:**
- Create: `sparkd/advisor/__init__.py` (empty)
- Create: `sparkd/advisor/prompts.py`
- Create: `sparkd/advisor/anthropic_adapter.py`
- Create: `tests/unit/test_advisor_prompt.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_advisor_prompt.py`:

```python
import json

from sparkd.advisor.prompts import (
    SYSTEM_PROMPT,
    build_recipe_prompt,
    build_optimize_prompt,
    build_mod_prompt,
    parse_recipe_draft,
    parse_mod_draft,
)
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec
from datetime import datetime, timezone


def _caps() -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=2,
        gpu_model="NVIDIA GB10",
        vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )


def _info() -> HFModelInfo:
    return HFModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct",
        architecture="LlamaForCausalLM",
        parameters_b=8.0,
        context_length=131072,
        supported_dtypes=["bf16"],
    )


def test_recipe_prompt_includes_facts():
    p = build_recipe_prompt(_info(), _caps())
    assert "GB10" in p
    assert "Llama-3.1-8B" in p
    assert "131072" in p


def test_optimize_prompt_carries_existing_recipe():
    r = RecipeSpec(name="r", model="m", args={"--tp": "1"})
    p = build_optimize_prompt(r, _caps(), goals=["throughput"])
    assert "--tp" in p
    assert "throughput" in p


def test_mod_prompt_carries_error_log():
    p = build_mod_prompt(error_log="ImportError: foo", model_id="x")
    assert "ImportError: foo" in p


def test_parse_recipe_draft_from_json_block():
    text = (
        "Here is the recipe.\n"
        '```json\n'
        '{"name":"r","model":"m","args":{"--tp":"2"},'
        '"env":{},"description":"d","rationale":"r"}\n'
        '```\n'
    )
    draft = parse_recipe_draft(text)
    assert draft.name == "r"
    assert draft.args["--tp"] == "2"


def test_parse_mod_draft_from_json_block():
    text = (
        '```json\n'
        '{"name":"m1","target_models":["llama"],'
        '"files":{"patch.diff":"--- a\\n+++ b\\n"},'
        '"description":"d","rationale":"r"}\n'
        '```'
    )
    d = parse_mod_draft(text)
    assert d.name == "m1"
    assert "patch.diff" in d.files


def test_system_prompt_describes_role():
    assert "DGX Spark" in SYSTEM_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_advisor_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sparkd/advisor/prompts.py`**

```python
from __future__ import annotations

import json
import re

from sparkd.schemas.advisor import ModDraft, RecipeDraft
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec


SYSTEM_PROMPT = """You are a vLLM deployment advisor for NVIDIA DGX Spark hardware.

Your job is to translate a Hugging Face model and a target box's hardware capabilities
into a concrete vLLM `serve` recipe (CLI args + env), or to optimize an existing recipe,
or to propose a model-specific patch ("mod") when a model needs a fix to run on vLLM.

Always emit your final answer as a single fenced ```json``` block matching the requested
schema. The recipe `args` keys must be the literal vLLM CLI flag names (e.g.
"--tensor-parallel-size", "--gpu-memory-utilization", "--max-model-len", "--quantization").
Values are strings.

Be conservative. Prefer settings that fit comfortably in available VRAM with a margin.
Explain trade-offs in `rationale` in one short paragraph.
"""


def _caps_block(caps: BoxCapabilities) -> str:
    return (
        f"Box capabilities:\n"
        f"- GPU model: {caps.gpu_model}\n"
        f"- GPU count: {caps.gpu_count}\n"
        f"- VRAM per GPU: {caps.vram_per_gpu_gb} GB\n"
        f"- CUDA: {caps.cuda_version or 'unknown'}\n"
        f"- IB iface: {caps.ib_interface or 'none'}\n"
    )


def _model_block(info: HFModelInfo) -> str:
    return (
        f"Hugging Face model facts:\n"
        f"- ID: {info.id}\n"
        f"- Architecture: {info.architecture or 'unknown'}\n"
        f"- Parameters: {info.parameters_b} B\n"
        f"- Context length: {info.context_length}\n"
        f"- Supported dtypes: {', '.join(info.supported_dtypes) or 'unknown'}\n"
        f"- License: {info.license or 'unknown'}\n"
    )


def build_recipe_prompt(info: HFModelInfo, caps: BoxCapabilities) -> str:
    return (
        _model_block(info)
        + "\n"
        + _caps_block(caps)
        + "\n"
        + "Produce a RecipeDraft as JSON with keys: "
        '`name` (slug derived from model), `model` (HF id), `args` (dict of '
        'CLI flag → value strings), `env` (dict), `description`, `rationale`.\n'
    )


def build_optimize_prompt(
    recipe: RecipeSpec, caps: BoxCapabilities, *, goals: list[str]
) -> str:
    return (
        f"Existing recipe:\n```yaml\n"
        f"name: {recipe.name}\nmodel: {recipe.model}\n"
        f"args: {json.dumps(recipe.args)}\nenv: {json.dumps(recipe.env)}\n"
        f"```\n\n"
        + _caps_block(caps)
        + f"\nGoals (in priority order): {', '.join(goals)}\n\n"
        "Return a revised RecipeDraft (same JSON shape as recipe creation). "
        "Keep the same `name` and `model`. Explain each change in `rationale`.\n"
    )


def build_mod_prompt(*, error_log: str, model_id: str) -> str:
    return (
        f"Model: {model_id}\n\n"
        f"Error log / failure mode:\n```\n{error_log}\n```\n\n"
        "Propose a vLLM mod (a small patch + optional shell hook) that fixes this. "
        "Return a ModDraft as JSON with keys: `name`, `target_models` (list), "
        "`files` (dict of relative-path → file-contents string; typically "
        "`patch.diff` with a unified diff and optionally `hook.sh`), "
        "`description`, `rationale`.\n"
    )


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> dict:
    m = _FENCE.search(text)
    if not m:
        # try whole text
        return json.loads(text)
    return json.loads(m.group(1))


def parse_recipe_draft(text: str) -> RecipeDraft:
    data = _extract_json(text)
    return RecipeDraft(**data)


def parse_mod_draft(text: str) -> ModDraft:
    data = _extract_json(text)
    return ModDraft(**data)
```

- [ ] **Step 4: Implement `sparkd/advisor/anthropic_adapter.py`**

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam

from sparkd.advisor.prompts import (
    SYSTEM_PROMPT,
    build_mod_prompt,
    build_optimize_prompt,
    build_recipe_prompt,
)
from sparkd.schemas.advisor import AdvisorMessage
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec


@dataclass
class AdvisorChunk:
    delta: str
    input_tokens: int = 0
    output_tokens: int = 0
    final: bool = False


class AdvisorPort(Protocol):
    async def stream_recipe(
        self, info: HFModelInfo, caps: BoxCapabilities, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]: ...

    async def stream_optimize(
        self, recipe: RecipeSpec, caps: BoxCapabilities, goals: list[str],
        history: list[AdvisorMessage],
    ) -> AsyncIterator[AdvisorChunk]: ...

    async def stream_mod(
        self, error_log: str, model_id: str, history: list[AdvisorMessage],
    ) -> AsyncIterator[AdvisorChunk]: ...


class AnthropicAdapter:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-opus-4-7",
        max_tokens: int = 4096,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def _stream(
        self, system: str, user: str, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]:
        messages: list[MessageParam] = []
        for m in history:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": user})
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    delta = getattr(event.delta, "text", "") or ""
                    if delta:
                        yield AdvisorChunk(delta=delta)
            final = await stream.get_final_message()
        usage = getattr(final, "usage", None)
        if usage is not None:
            yield AdvisorChunk(
                delta="",
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                final=True,
            )
        else:
            yield AdvisorChunk(delta="", final=True)

    async def stream_recipe(
        self, info: HFModelInfo, caps: BoxCapabilities, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]:
        async for c in self._stream(SYSTEM_PROMPT, build_recipe_prompt(info, caps), history):
            yield c

    async def stream_optimize(
        self, recipe: RecipeSpec, caps: BoxCapabilities, goals: list[str],
        history: list[AdvisorMessage],
    ) -> AsyncIterator[AdvisorChunk]:
        prompt = build_optimize_prompt(recipe, caps, goals=goals)
        async for c in self._stream(SYSTEM_PROMPT, prompt, history):
            yield c

    async def stream_mod(
        self, error_log: str, model_id: str, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]:
        prompt = build_mod_prompt(error_log=error_log, model_id=model_id)
        async for c in self._stream(SYSTEM_PROMPT, prompt, history):
            yield c
```

`sparkd/advisor/__init__.py`:

```python
from sparkd.advisor.anthropic_adapter import AdvisorChunk, AdvisorPort, AnthropicAdapter

__all__ = ["AdvisorChunk", "AdvisorPort", "AnthropicAdapter"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_advisor_prompt.py -v`
Expected: PASS, 7 passed.

- [ ] **Step 6: Commit**

```bash
git add sparkd/advisor tests/unit/test_advisor_prompt.py
git commit -m "feat: AdvisorPort + AnthropicAdapter (streaming, prompt caching)"
```

---

## Task 5: AdvisorService

**Files:**
- Create: `sparkd/services/advisor.py`
- Create: `tests/integration/test_advisor_service.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_advisor_service.py`:

```python
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from sparkd.advisor import AdvisorChunk
from sparkd.db.engine import init_engine
from sparkd.schemas.advisor import AdvisorMessage
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.services.advisor import AdvisorService


class FakePort:
    def __init__(self, text: str, *, in_tok: int = 5, out_tok: int = 10) -> None:
        self.text = text
        self.in_tok = in_tok
        self.out_tok = out_tok
        self.last_history: list[AdvisorMessage] = []

    async def _yield(self, history) -> AsyncIterator[AdvisorChunk]:
        self.last_history = list(history)
        for ch in self.text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=self.in_tok, output_tokens=self.out_tok, final=True)

    async def stream_recipe(self, info, caps, history):
        async for c in self._yield(history):
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield(history):
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield(history):
            yield c


@pytest.fixture
async def svc(sparkd_home):
    await init_engine(create_all=True)
    text = (
        '```json\n{"name":"llama","model":"meta-llama/Llama-3.1-8B-Instruct",'
        '"args":{"--tensor-parallel-size":"2"},"env":{},"description":"d","rationale":"r"}\n```'
    )
    port = FakePort(text)
    yield AdvisorService(port=port), port


async def test_generate_recipe_yields_tokens_then_draft(svc):
    s, port = svc
    info = HFModelInfo(id="meta-llama/Llama-3.1-8B-Instruct", architecture="X", parameters_b=8.0, context_length=131072)
    caps = BoxCapabilities(
        gpu_count=2, gpu_model="GB10", vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )
    sid = await s.create_session(kind="recipe", target_box_id="b1", hf_model_id=info.id)
    deltas: list[str] = []
    final_draft = None
    async for ev in s.generate_recipe(sid, info=info, caps=caps):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            final_draft = ev["draft"]
    assert "".join(deltas)
    assert final_draft is not None
    assert final_draft["name"] == "llama"
    assert final_draft["args"]["--tensor-parallel-size"] == "2"


async def test_followup_appends_message_and_calls_port(svc):
    s, port = svc
    sid = await s.create_session(kind="recipe", hf_model_id="x/y")
    info = HFModelInfo(id="x/y", architecture="X", parameters_b=1.0, context_length=4096)
    caps = BoxCapabilities(
        gpu_count=1, gpu_model="GB10", vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )
    async for _ in s.generate_recipe(sid, info=info, caps=caps):
        pass
    # follow-up
    async for _ in s.followup(sid, "tweak it for lower latency", info=info, caps=caps):
        pass
    history_roles = [m.role for m in port.last_history]
    assert "user" in history_roles
    assert "assistant" in history_roles


async def test_get_session_returns_persisted_messages(svc):
    s, _port = svc
    info = HFModelInfo(id="x/y", architecture="X", parameters_b=1.0, context_length=4096)
    caps = BoxCapabilities(
        gpu_count=1, gpu_model="GB10", vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )
    sid = await s.create_session(kind="recipe", hf_model_id="x/y")
    async for _ in s.generate_recipe(sid, info=info, caps=caps):
        pass
    sess = await s.get_session(sid)
    assert sess.id == sid
    assert sess.input_tokens > 0
    assert any(m.role == "assistant" for m in sess.messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_advisor_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sparkd/services/advisor.py`**

```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select

from sparkd.advisor import AdvisorPort
from sparkd.db.engine import session_scope
from sparkd.db.models import AdvisorSessionRow
from sparkd.errors import NotFoundError, UpstreamError
from sparkd.schemas.advisor import (
    AdvisorMessage,
    AdvisorSession,
    ModDraft,
    RecipeDraft,
)
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec
from sparkd.advisor.prompts import parse_mod_draft, parse_recipe_draft


def _row_to_session(row: AdvisorSessionRow) -> AdvisorSession:
    return AdvisorSession(
        id=row.id,
        kind=row.kind,
        target_box_id=row.target_box_id,
        target_recipe_name=row.target_recipe_name,
        hf_model_id=row.hf_model_id,
        messages=[AdvisorMessage(**m) for m in (row.messages_json or [])],
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        created_at=row.created_at,
    )


class AdvisorService:
    def __init__(self, port: AdvisorPort) -> None:
        self.port = port

    async def create_session(
        self,
        *,
        kind: str,
        target_box_id: str | None = None,
        target_recipe_name: str | None = None,
        hf_model_id: str | None = None,
    ) -> str:
        sid = uuid.uuid4().hex[:12]
        async with session_scope() as s:
            s.add(
                AdvisorSessionRow(
                    id=sid,
                    kind=kind,
                    target_box_id=target_box_id,
                    target_recipe_name=target_recipe_name,
                    hf_model_id=hf_model_id,
                    messages_json=[],
                )
            )
        return sid

    async def get_session(self, session_id: str) -> AdvisorSession:
        async with session_scope() as s:
            row = await s.get(AdvisorSessionRow, session_id)
            if row is None:
                raise NotFoundError("advisor_session", session_id)
            return _row_to_session(row)

    async def _load_history(self, session_id: str) -> list[AdvisorMessage]:
        sess = await self.get_session(session_id)
        return sess.messages

    async def _persist_turn(
        self,
        session_id: str,
        *,
        user_msg: str,
        assistant_text: str,
        in_tokens: int,
        out_tokens: int,
    ) -> None:
        async with session_scope() as s:
            row = await s.get(AdvisorSessionRow, session_id)
            if row is None:
                raise NotFoundError("advisor_session", session_id)
            existing = list(row.messages_json or [])
            existing.append({"role": "user", "content": user_msg})
            existing.append({"role": "assistant", "content": assistant_text})
            row.messages_json = existing
            row.input_tokens = (row.input_tokens or 0) + in_tokens
            row.output_tokens = (row.output_tokens or 0) + out_tokens

    async def _drive(
        self,
        session_id: str,
        user_msg: str,
        chunks_iter: AsyncIterator,
        parse_kind: str,
    ) -> AsyncIterator[dict[str, Any]]:
        buf: list[str] = []
        in_tok = 0
        out_tok = 0
        async for ch in chunks_iter:
            if ch.final:
                in_tok = ch.input_tokens
                out_tok = ch.output_tokens
                continue
            if ch.delta:
                buf.append(ch.delta)
                yield {"type": "delta", "text": ch.delta}
        full = "".join(buf)
        await self._persist_turn(
            session_id,
            user_msg=user_msg,
            assistant_text=full,
            in_tokens=in_tok,
            out_tokens=out_tok,
        )
        try:
            if parse_kind == "recipe":
                draft = parse_recipe_draft(full)
                yield {"type": "draft", "draft": draft.model_dump()}
            elif parse_kind == "mod":
                draft = parse_mod_draft(full)
                yield {"type": "draft", "draft": draft.model_dump()}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"could not parse {parse_kind}: {exc}"}

    async def generate_recipe(
        self,
        session_id: str,
        *,
        info: HFModelInfo,
        caps: BoxCapabilities,
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        history = await self._load_history(session_id)
        msg = user_msg or f"Generate a recipe for {info.id}"
        try:
            chunks = self.port.stream_recipe(info=info, caps=caps, history=history)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "recipe"):
            yield ev

    async def optimize_recipe(
        self,
        session_id: str,
        *,
        recipe: RecipeSpec,
        caps: BoxCapabilities,
        goals: list[str],
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        history = await self._load_history(session_id)
        msg = user_msg or f"Optimize recipe {recipe.name} for goals: {', '.join(goals)}"
        try:
            chunks = self.port.stream_optimize(
                recipe=recipe, caps=caps, goals=goals, history=history
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "recipe"):
            yield ev

    async def propose_mod(
        self,
        session_id: str,
        *,
        error_log: str,
        model_id: str,
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        history = await self._load_history(session_id)
        msg = user_msg or f"Propose a mod for {model_id} addressing the error log."
        try:
            chunks = self.port.stream_mod(
                error_log=error_log, model_id=model_id, history=history
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "mod"):
            yield ev

    async def followup(
        self,
        session_id: str,
        message: str,
        *,
        info: HFModelInfo | None = None,
        caps: BoxCapabilities | None = None,
        recipe: RecipeSpec | None = None,
        goals: list[str] | None = None,
        error_log: str | None = None,
        model_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        sess = await self.get_session(session_id)
        history = sess.messages
        if sess.kind == "recipe" and info and caps:
            chunks = self.port.stream_recipe(info=info, caps=caps, history=history)
            parse = "recipe"
        elif sess.kind == "optimize" and recipe and caps:
            chunks = self.port.stream_optimize(
                recipe=recipe, caps=caps, goals=goals or [], history=history
            )
            parse = "recipe"
        elif sess.kind == "mod" and error_log and model_id:
            chunks = self.port.stream_mod(
                error_log=error_log, model_id=model_id, history=history
            )
            parse = "mod"
        else:
            raise UpstreamError(f"missing context for follow-up on session {session_id}")
        async for ev in self._drive(session_id, message, chunks, parse):
            yield ev
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_advisor_service.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/advisor.py tests/integration/test_advisor_service.py
git commit -m "feat: AdvisorService — sessions, streaming, parse drafts"
```

---

## Task 6: ModService

**Files:**
- Create: `sparkd/services/mod.py`
- Create: `tests/unit/test_mod_service.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_mod_service.py`:

```python
import pytest

from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.mod import ModSpec
from sparkd.services.mod import ModService


@pytest.fixture
def svc(sparkd_home):
    return ModService()


def test_save_then_load_mod(svc):
    m = ModSpec(
        name="patch-a",
        target_models=["llama"],
        description="d",
        files={"patch.diff": "--- a\n+++ b\n", "hook.sh": "#!/bin/sh\n"},
    )
    svc.save(m)
    got = svc.load("patch-a")
    assert got.files["patch.diff"].startswith("--- a")


def test_list_returns_all(svc):
    svc.save(ModSpec(name="a", target_models=[]))
    svc.save(ModSpec(name="b", target_models=[]))
    names = sorted(m.name for m in svc.list())
    assert names == ["a", "b"]


def test_load_missing_raises(svc):
    with pytest.raises(NotFoundError):
        svc.load("nope")


def test_save_rejects_traversal(svc):
    with pytest.raises(ValidationError):
        svc.save(ModSpec(name="../evil", target_models=[]))


def test_save_rejects_traversal_in_filename(svc):
    with pytest.raises(ValidationError):
        svc.save(
            ModSpec(name="m", target_models=[], files={"../etc/passwd": "x"})
        )


def test_delete_mod(svc):
    svc.save(ModSpec(name="a", target_models=[]))
    svc.delete("a")
    with pytest.raises(NotFoundError):
        svc.load("a")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_mod_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sparkd/services/mod.py`**

```python
from __future__ import annotations

import re
from pathlib import Path

import yaml

from sparkd import paths
from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.mod import ModSpec


_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-./]{0,127}$")


def _check_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValidationError(f"invalid mod name: {name!r}")


def _check_filename(name: str) -> None:
    if not _FILENAME_RE.match(name) or ".." in name or name.startswith("/"):
        raise ValidationError(f"invalid mod file path: {name!r}")


class ModService:
    def __init__(self) -> None:
        paths.ensure()

    def _dir(self, name: str) -> Path:
        return paths.library() / "mods" / name

    def save(self, spec: ModSpec) -> None:
        _check_name(spec.name)
        for f in spec.files:
            _check_filename(f)
        d = self._dir(spec.name)
        d.mkdir(parents=True, exist_ok=True)
        meta = {
            "name": spec.name,
            "target_models": spec.target_models,
            "description": spec.description,
            "enabled": spec.enabled,
        }
        (d / "mod.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
        for fname, content in spec.files.items():
            target = d / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    def load(self, name: str) -> ModSpec:
        _check_name(name)
        d = self._dir(name)
        meta_path = d / "mod.yaml"
        if not meta_path.exists():
            raise NotFoundError("mod", name)
        meta = yaml.safe_load(meta_path.read_text()) or {}
        files: dict[str, str] = {}
        for p in d.rglob("*"):
            if not p.is_file() or p.name == "mod.yaml":
                continue
            rel = str(p.relative_to(d))
            files[rel] = p.read_text()
        return ModSpec(
            name=meta.get("name", name),
            target_models=list(meta.get("target_models") or []),
            description=meta.get("description", "") or "",
            files=files,
            enabled=bool(meta.get("enabled", True)),
        )

    def list(self) -> list[ModSpec]:
        root = paths.library() / "mods"
        if not root.exists():
            return []
        out: list[ModSpec] = []
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "mod.yaml").exists():
                out.append(self.load(d.name))
        return out

    def delete(self, name: str) -> None:
        _check_name(name)
        d = self._dir(name)
        if not d.exists():
            raise NotFoundError("mod", name)
        for p in sorted(d.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        d.rmdir()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_mod_service.py -v`
Expected: PASS, 6 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/mod.py tests/unit/test_mod_service.py
git commit -m "feat: ModService — directory-backed mod CRUD with path-traversal guard"
```

---

## Task 7: HF routes

**Files:**
- Create: `sparkd/routes/hf.py`
- Modify: `sparkd/app.py` (wire HFCatalogService + router)
- Create: `tests/integration/test_hf_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_hf_routes.py`:

```python
import httpx
import pytest
import respx
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
    await app.state.pool.close_all()


@respx.mock
async def test_get_hf_model_returns_facts(client):
    respx.get("https://huggingface.co/api/models/x/y").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "x/y",
                "pipeline_tag": "text-generation",
                "config": {"architectures": ["A"], "max_position_embeddings": 4096},
                "safetensors": {"total": 2_000_000_000},
            },
        )
    )
    r = await client.get("/hf/models/x/y")
    assert r.status_code == 200
    body = r.json()
    assert body["architecture"] == "A"
    assert body["context_length"] == 4096


@respx.mock
async def test_get_hf_model_missing_returns_minimal(client):
    respx.get("https://huggingface.co/api/models/missing/x").mock(
        return_value=httpx.Response(404, json={})
    )
    r = await client.get("/hf/models/missing/x")
    assert r.status_code == 200
    assert r.json()["id"] == "missing/x"
```

- [ ] **Step 2: Implement `sparkd/routes/hf.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sparkd.services.hf_catalog import HFCatalogService

router = APIRouter(prefix="/hf", tags=["hf"])


def _svc(request: Request) -> HFCatalogService:
    return request.app.state.hf


@router.get("/models/{model_id:path}")
async def get_hf_model(model_id: str, svc: HFCatalogService = Depends(_svc)) -> dict:
    info = await svc.fetch(model_id)
    return info.model_dump(mode="json")
```

- [ ] **Step 3: Modify `sparkd/app.py`**

Add the import (alongside the other route imports):

```python
from sparkd.routes.hf import router as hf_router
from sparkd.services.hf_catalog import HFCatalogService
```

In `build_app`, after `app.state.status = StatusService(...)`:

```python
    app.state.hf = HFCatalogService()
```

In the include list:

```python
    app.include_router(hf_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_hf_routes.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/routes/hf.py sparkd/app.py tests/integration/test_hf_routes.py
git commit -m "feat: /hf/models/{id} route + HFCatalogService wired"
```

---

## Task 8: Mod routes

**Files:**
- Create: `sparkd/routes/mods.py`
- Modify: `sparkd/app.py` (wire ModService + router)
- Create: `tests/integration/test_mod_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_mod_routes.py`:

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
    await app.state.pool.close_all()


async def test_create_list_get_delete_mod(client):
    body = {
        "name": "patch-a",
        "target_models": ["llama"],
        "description": "fix vocab",
        "files": {"patch.diff": "--- a\n+++ b\n"},
        "enabled": True,
    }
    r = await client.post("/mods", json=body)
    assert r.status_code == 201
    r = await client.get("/mods")
    assert r.status_code == 200
    assert any(m["name"] == "patch-a" for m in r.json())
    r = await client.get("/mods/patch-a")
    assert r.status_code == 200
    assert r.json()["files"]["patch.diff"].startswith("--- a")
    r = await client.delete("/mods/patch-a")
    assert r.status_code == 204
    assert (await client.get("/mods/patch-a")).status_code == 404


async def test_create_mod_invalid_name_returns_422(client):
    r = await client.post(
        "/mods",
        json={"name": "../evil", "target_models": [], "files": {}},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Implement `sparkd/routes/mods.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from sparkd.errors import ValidationError
from sparkd.schemas.mod import ModSpec
from sparkd.services.mod import ModService

router = APIRouter(prefix="/mods", tags=["mods"])


def _svc(request: Request) -> ModService:
    return request.app.state.mods


@router.get("", response_model=list[ModSpec])
def list_mods(svc: ModService = Depends(_svc)) -> list[ModSpec]:
    return svc.list()


@router.post("", response_model=ModSpec, status_code=201)
def create_mod(spec: ModSpec, svc: ModService = Depends(_svc)) -> ModSpec:
    svc.save(spec)
    return spec


@router.get("/{name}", response_model=ModSpec)
def get_mod(name: str, svc: ModService = Depends(_svc)) -> ModSpec:
    return svc.load(name)


@router.put("/{name}", response_model=ModSpec)
def put_mod(name: str, spec: ModSpec, svc: ModService = Depends(_svc)) -> ModSpec:
    if spec.name != name:
        raise ValidationError("path name and body name disagree")
    svc.save(spec)
    return spec


@router.delete("/{name}", status_code=204)
def delete_mod(name: str, svc: ModService = Depends(_svc)) -> Response:
    svc.delete(name)
    return Response(status_code=204)
```

- [ ] **Step 3: Modify `sparkd/app.py`**

Add the import:

```python
from sparkd.routes.mods import router as mods_router
from sparkd.services.mod import ModService
```

In `build_app`, after `app.state.hf = HFCatalogService()`:

```python
    app.state.mods = ModService()
```

Include the router:

```python
    app.include_router(mods_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_mod_routes.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/routes/mods.py sparkd/app.py tests/integration/test_mod_routes.py
git commit -m "feat: /mods CRUD route + ModService wired"
```

---

## Task 9: Advisor routes (REST + WebSocket)

**Files:**
- Create: `sparkd/routes/advisor.py`
- Modify: `sparkd/routes/ws.py` (add `/ws/advisor/{session}`)
- Modify: `sparkd/app.py` (wire AdvisorService + router; pick port from secrets)
- Create: `tests/integration/test_advisor_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_advisor_routes.py`:

```python
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from sparkd.advisor import AdvisorChunk
from sparkd.app import build_app
from sparkd.db.engine import init_engine


class FakePort:
    def __init__(self, text: str) -> None:
        self.text = text

    async def _yield(self) -> AsyncIterator[AdvisorChunk]:
        for ch in self.text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=4, output_tokens=8, final=True)

    async def stream_recipe(self, info, caps, history):
        async for c in self._yield():
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield():
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield():
            yield c


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()
    text = (
        '```json\n{"name":"r1","model":"x/y",'
        '"args":{"--tp":"1"},"env":{},"description":"d","rationale":"r"}\n```'
    )
    app.state.advisor.port = FakePort(text)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


@respx.mock
async def test_create_session_then_generate_recipe(client):
    c, _app = client
    respx.get("https://huggingface.co/api/models/x/y").mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "x/y",
                "config": {"architectures": ["A"], "max_position_embeddings": 4096},
                "safetensors": {"total": 1_000_000_000},
            },
        )
    )
    r = await c.post(
        "/advisor/sessions", json={"kind": "recipe", "hf_model_id": "x/y"}
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    # generate (non-streaming variant returns full draft)
    r = await c.post(f"/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["draft"]["name"] == "r1"
    # session persisted
    r = await c.get(f"/advisor/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["input_tokens"] == 4
    assert r.json()["output_tokens"] == 8
```

- [ ] **Step 2: Implement `sparkd/routes/advisor.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from sparkd.errors import ValidationError
from sparkd.schemas.advisor import AdvisorSession
from sparkd.services.advisor import AdvisorService
from sparkd.services.box import BoxService
from sparkd.services.hf_catalog import HFCatalogService
from sparkd.services.library import LibraryService

router = APIRouter(prefix="/advisor", tags=["advisor"])


def _svc(request: Request) -> AdvisorService:
    return request.app.state.advisor


def _hf(request: Request) -> HFCatalogService:
    return request.app.state.hf


def _boxes(request: Request) -> BoxService:
    return request.app.state.boxes


def _lib(request: Request) -> LibraryService:
    return request.app.state.library


class CreateSessionBody(BaseModel):
    kind: str
    target_box_id: str | None = None
    target_recipe_name: str | None = None
    hf_model_id: str | None = None


class CreateSessionResponse(BaseModel):
    id: str


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionBody, svc: AdvisorService = Depends(_svc)
) -> CreateSessionResponse:
    if body.kind not in {"recipe", "optimize", "mod"}:
        raise ValidationError(f"invalid kind: {body.kind!r}")
    sid = await svc.create_session(
        kind=body.kind,
        target_box_id=body.target_box_id,
        target_recipe_name=body.target_recipe_name,
        hf_model_id=body.hf_model_id,
    )
    return CreateSessionResponse(id=sid)


@router.get("/sessions/{session_id}", response_model=AdvisorSession)
async def get_session(
    session_id: str, svc: AdvisorService = Depends(_svc)
) -> AdvisorSession:
    return await svc.get_session(session_id)


class GenerateRecipeBody(BaseModel):
    user_msg: str | None = None


@router.post("/sessions/{session_id}/recipe")
async def generate_recipe(
    session_id: str,
    body: GenerateRecipeBody,
    svc: AdvisorService = Depends(_svc),
    hf: HFCatalogService = Depends(_hf),
    boxes: BoxService = Depends(_boxes),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.hf_model_id:
        raise ValidationError("session has no hf_model_id")
    info = await hf.fetch(sess.hf_model_id)
    if not sess.target_box_id:
        raise ValidationError("session has no target_box_id")
    caps = await boxes.capabilities(sess.target_box_id)
    draft = None
    deltas: list[str] = []
    async for ev in svc.generate_recipe(
        session_id, info=info, caps=caps, user_msg=body.user_msg
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}


class OptimizeBody(BaseModel):
    goals: list[str] = Field(default_factory=list)
    user_msg: str | None = None


@router.post("/sessions/{session_id}/optimize")
async def optimize_recipe(
    session_id: str,
    body: OptimizeBody,
    svc: AdvisorService = Depends(_svc),
    boxes: BoxService = Depends(_boxes),
    lib: LibraryService = Depends(_lib),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.target_recipe_name or not sess.target_box_id:
        raise ValidationError("session needs target_recipe_name and target_box_id")
    recipe = lib.load_recipe(sess.target_recipe_name, box_id=sess.target_box_id)
    caps = await boxes.capabilities(sess.target_box_id)
    draft = None
    deltas: list[str] = []
    async for ev in svc.optimize_recipe(
        session_id, recipe=recipe, caps=caps,
        goals=body.goals, user_msg=body.user_msg,
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}


class ProposeModBody(BaseModel):
    error_log: str
    user_msg: str | None = None


@router.post("/sessions/{session_id}/mod")
async def propose_mod(
    session_id: str,
    body: ProposeModBody,
    svc: AdvisorService = Depends(_svc),
) -> dict:
    sess = await svc.get_session(session_id)
    if not sess.hf_model_id:
        raise ValidationError("session has no hf_model_id")
    draft = None
    deltas: list[str] = []
    async for ev in svc.propose_mod(
        session_id, error_log=body.error_log,
        model_id=sess.hf_model_id, user_msg=body.user_msg,
    ):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            draft = ev["draft"]
        elif ev["type"] == "error":
            raise ValidationError(ev["message"])
    return {"draft": draft, "text": "".join(deltas)}
```

- [ ] **Step 3: Add WS endpoint to `sparkd/routes/ws.py`**

Append to the file:

```python
@router.websocket("/ws/advisor/{session_id}")
async def advisor_stream(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    svc = ws.app.state.advisor
    hf = ws.app.state.hf
    boxes = ws.app.state.boxes
    sess = await svc.get_session(session_id)
    try:
        if sess.kind == "recipe" and sess.hf_model_id and sess.target_box_id:
            info = await hf.fetch(sess.hf_model_id)
            caps = await boxes.capabilities(sess.target_box_id)
            stream = svc.generate_recipe(session_id, info=info, caps=caps)
        else:
            await ws.send_json({"type": "error", "message": "missing context"})
            await ws.close(code=1003)
            return
        async for ev in stream:
            await ws.send_json(ev)
        await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close(code=1011)
```

- [ ] **Step 4: Modify `sparkd/app.py`** to wire AdvisorService + adapter

Add imports:

```python
from sparkd.advisor import AnthropicAdapter
from sparkd.routes.advisor import router as advisor_router
from sparkd.services.advisor import AdvisorService
from sparkd import secrets as sparkd_secrets
```

In `build_app`, after `app.state.mods = ModService()`:

```python
    api_key = sparkd_secrets.get_secret("anthropic_api_key") or ""
    if api_key:
        port = AnthropicAdapter(api_key=api_key)
    else:
        port = None  # tests inject a fake; production user runs setup wizard
    app.state.advisor = AdvisorService(port=port) if port else AdvisorService.__new__(AdvisorService)
    if not port:
        # placeholder service; routes will 500 on use until key set
        app.state.advisor.port = None
```

(In tests we override `app.state.advisor.port` with a `FakePort` after `build_app` returns.)

Include the router:

```python
    app.include_router(advisor_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_advisor_routes.py -v`
Expected: PASS, 1 passed.

- [ ] **Step 6: Commit**

```bash
git add sparkd/routes/advisor.py sparkd/routes/ws.py sparkd/app.py tests/integration/test_advisor_routes.py
git commit -m "feat: /advisor REST + WS routes wired through AnthropicAdapter"
```

---

## Task 10: First-run setup endpoint for Anthropic key

**Files:**
- Modify: `sparkd/routes/advisor.py` (add /advisor/setup)
- Create: `tests/integration/test_advisor_setup.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_advisor_setup.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sparkd.app import build_app
from sparkd.db.engine import init_engine


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr(
        "sparkd.secrets._backend_set",
        lambda svc, k, v: store.__setitem__((svc, k), v),
    )
    monkeypatch.setattr(
        "sparkd.secrets._backend_get", lambda svc, k: store.get((svc, k))
    )
    await init_engine(create_all=True)
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store
    await app.state.pool.close_all()


async def test_setup_persists_key_and_status_reports_configured(client):
    c, store = client
    r = await c.post("/advisor/setup", json={"anthropic_api_key": "sk-test"})
    assert r.status_code == 200
    assert store[("sparkd", "anthropic_api_key")] == "sk-test"
    r = await c.get("/advisor/status")
    assert r.json()["configured"] is True
```

- [ ] **Step 2: Add to `sparkd/routes/advisor.py`**

```python
from sparkd import secrets as sparkd_secrets
from sparkd.advisor import AnthropicAdapter


class SetupBody(BaseModel):
    anthropic_api_key: str


@router.post("/setup")
def setup(body: SetupBody, request: Request) -> dict:
    if not body.anthropic_api_key.strip():
        raise ValidationError("anthropic_api_key is required")
    sparkd_secrets.set_secret("anthropic_api_key", body.anthropic_api_key.strip())
    request.app.state.advisor.port = AnthropicAdapter(api_key=body.anthropic_api_key.strip())
    return {"ok": True}


@router.get("/status")
def status(request: Request) -> dict:
    port = getattr(request.app.state.advisor, "port", None)
    return {"configured": port is not None}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_advisor_setup.py -v`
Expected: PASS, 1 passed.

- [ ] **Step 4: Commit**

```bash
git add sparkd/routes/advisor.py tests/integration/test_advisor_setup.py
git commit -m "feat: /advisor/setup + /advisor/status (first-run Anthropic key)"
```

---

## Task 11: Frontend hooks for HF, mods, advisor

**Files:**
- Create: `frontend/src/hooks/useHF.ts`
- Create: `frontend/src/hooks/useMods.ts`
- Create: `frontend/src/hooks/useAdvisor.ts`

- [ ] **Step 1: Implement `frontend/src/hooks/useHF.ts`**

```ts
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export type HFModelInfo = {
  id: string;
  architecture: string;
  parameters_b: number;
  context_length: number;
  supported_dtypes: string[];
  license: string;
  pipeline_tag: string;
};

export function useHFModel(id: string | null) {
  return useQuery({
    queryKey: ["hf", id],
    queryFn: () => api.get<HFModelInfo>(`/hf/models/${id}`),
    enabled: !!id,
  });
}
```

- [ ] **Step 2: Implement `frontend/src/hooks/useMods.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Mod = {
  name: string;
  target_models: string[];
  description: string;
  files: Record<string, string>;
  enabled: boolean;
};

export function useMods() {
  return useQuery({ queryKey: ["mods"], queryFn: () => api.get<Mod[]>("/mods") });
}

export function useSaveMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (m: Mod) => api.post<Mod>("/mods", m),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}

export function useDeleteMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/mods/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}
```

- [ ] **Step 3: Implement `frontend/src/hooks/useAdvisor.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type AdvisorSession = {
  id: string;
  kind: "recipe" | "optimize" | "mod";
  target_box_id: string | null;
  target_recipe_name: string | null;
  hf_model_id: string | null;
  messages: Array<{ role: string; content: string }>;
  input_tokens: number;
  output_tokens: number;
};

export type RecipeDraft = {
  name: string;
  model: string;
  args: Record<string, string>;
  env: Record<string, string>;
  description: string;
  rationale: string;
};

export type ModDraft = {
  name: string;
  target_models: string[];
  files: Record<string, string>;
  description: string;
  rationale: string;
};

export function useAdvisorStatus() {
  return useQuery({
    queryKey: ["advisor", "status"],
    queryFn: () => api.get<{ configured: boolean }>("/advisor/status"),
  });
}

export function useAdvisorSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { anthropic_api_key: string }) =>
      api.post<{ ok: boolean }>("/advisor/setup", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["advisor", "status"] }),
  });
}

export function useCreateAdvisorSession() {
  return useMutation({
    mutationFn: (body: {
      kind: "recipe" | "optimize" | "mod";
      target_box_id?: string | null;
      target_recipe_name?: string | null;
      hf_model_id?: string | null;
    }) => api.post<{ id: string }>("/advisor/sessions", body),
  });
}

export function useGenerateRecipe() {
  return useMutation({
    mutationFn: (sid: string) =>
      api.post<{ draft: RecipeDraft; text: string }>(
        `/advisor/sessions/${sid}/recipe`,
        {}
      ),
  });
}

export function useOptimizeRecipe() {
  return useMutation({
    mutationFn: ({
      sid,
      goals,
    }: {
      sid: string;
      goals: string[];
    }) =>
      api.post<{ draft: RecipeDraft; text: string }>(
        `/advisor/sessions/${sid}/optimize`,
        { goals }
      ),
  });
}

export function useProposeMod() {
  return useMutation({
    mutationFn: ({ sid, error_log }: { sid: string; error_log: string }) =>
      api.post<{ draft: ModDraft; text: string }>(
        `/advisor/sessions/${sid}/mod`,
        { error_log }
      ),
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useHF.ts frontend/src/hooks/useMods.ts frontend/src/hooks/useAdvisor.ts
git commit -m "feat(frontend): hooks for HF, mods, advisor"
```

---

## Task 12: Frontend components — RecipeDraftPane, ModDraftPane, AdvisorChat

**Files:**
- Create: `frontend/src/components/RecipeDraftPane.tsx`
- Create: `frontend/src/components/ModDraftPane.tsx`
- Create: `frontend/src/components/AdvisorChat.tsx`

- [ ] **Step 1: Implement `frontend/src/components/RecipeDraftPane.tsx`**

```tsx
import { RecipeDraft } from "../hooks/useAdvisor";
import { useSaveRecipe } from "../hooks/useRecipes";

export default function RecipeDraftPane({ draft }: { draft: RecipeDraft }) {
  const save = useSaveRecipe();
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
      <h3>{draft.name}</h3>
      <p>
        <b>Model:</b> {draft.model}
      </p>
      <p>{draft.description}</p>
      <table>
        <tbody>
          {Object.entries(draft.args).map(([k, v]) => (
            <tr key={k}>
              <td>
                <code>{k}</code>
              </td>
              <td>
                <code>{v}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <i>{draft.rationale}</i>
      </p>
      <button
        onClick={() =>
          save.mutate({
            name: draft.name,
            model: draft.model,
            args: draft.args,
            env: draft.env,
            mods: [],
          })
        }
      >
        save recipe
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Implement `frontend/src/components/ModDraftPane.tsx`**

```tsx
import { ModDraft } from "../hooks/useAdvisor";
import { useSaveMod } from "../hooks/useMods";

export default function ModDraftPane({ draft }: { draft: ModDraft }) {
  const save = useSaveMod();
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
      <h3>{draft.name}</h3>
      <p>{draft.description}</p>
      <p>
        targets: <code>{draft.target_models.join(", ")}</code>
      </p>
      {Object.entries(draft.files).map(([f, c]) => (
        <details key={f}>
          <summary>{f}</summary>
          <pre style={{ background: "#f5f5f5", padding: 8 }}>{c}</pre>
        </details>
      ))}
      <p>
        <i>{draft.rationale}</i>
      </p>
      <button
        onClick={() =>
          save.mutate({
            name: draft.name,
            target_models: draft.target_models,
            description: draft.description,
            files: draft.files,
            enabled: true,
          })
        }
      >
        save mod
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Implement `frontend/src/components/AdvisorChat.tsx`**

```tsx
export default function AdvisorChat({
  text,
  loading,
}: {
  text: string;
  loading: boolean;
}) {
  return (
    <pre
      style={{
        background: "#111",
        color: "#eee",
        padding: 12,
        minHeight: 120,
        whiteSpace: "pre-wrap",
        fontFamily: "ui-monospace, monospace",
      }}
    >
      {text}
      {loading && <span style={{ opacity: 0.6 }}>▌</span>}
    </pre>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecipeDraftPane.tsx frontend/src/components/ModDraftPane.tsx frontend/src/components/AdvisorChat.tsx
git commit -m "feat(frontend): RecipeDraftPane, ModDraftPane, AdvisorChat"
```

---

## Task 13: AdvisorPage, OptimizePage, ModsPage + setup gate

**Files:**
- Create: `frontend/src/pages/AdvisorPage.tsx`
- Create: `frontend/src/pages/OptimizePage.tsx`
- Create: `frontend/src/pages/ModsPage.tsx`
- Modify: `frontend/src/App.tsx` (nav links + routes)

- [ ] **Step 1: Implement `frontend/src/pages/AdvisorPage.tsx`**

```tsx
import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import RecipeDraftPane from "../components/RecipeDraftPane";
import { useBoxes } from "../hooks/useBoxes";
import {
  RecipeDraft,
  useAdvisorSetup,
  useAdvisorStatus,
  useCreateAdvisorSession,
  useGenerateRecipe,
} from "../hooks/useAdvisor";

function SetupGate({ children }: { children: React.ReactNode }) {
  const status = useAdvisorStatus();
  const setup = useAdvisorSetup();
  const [key, setKey] = useState("");
  if (status.isLoading) return <div>loading…</div>;
  if (status.data?.configured) return <>{children}</>;
  return (
    <div>
      <h2>Connect to Anthropic</h2>
      <p>Paste your Anthropic API key (stored in OS keyring).</p>
      <input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="sk-ant-..."
        style={{ width: 360 }}
      />{" "}
      <button
        disabled={!key}
        onClick={() => setup.mutate({ anthropic_api_key: key })}
      >
        save
      </button>
    </div>
  );
}

export default function AdvisorPage() {
  const boxes = useBoxes();
  const [boxId, setBoxId] = useState("");
  const [hfId, setHfId] = useState("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const gen = useGenerateRecipe();
  const busy = create.isPending || gen.isPending;
  return (
    <SetupGate>
      <h1>Advisor — generate recipe</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
          <option value="">-- target box --</option>
          {(boxes.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          placeholder="huggingface/model-id"
          value={hfId}
          onChange={(e) => setHfId(e.target.value)}
          style={{ minWidth: 280 }}
        />
        <button
          disabled={!boxId || !hfId || busy}
          onClick={async () => {
            setText("");
            setDraft(null);
            const r = await create.mutateAsync({
              kind: "recipe",
              target_box_id: boxId,
              hf_model_id: hfId,
            });
            const out = await gen.mutateAsync(r.id);
            setText(out.text);
            setDraft(out.draft);
          }}
        >
          generate
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <RecipeDraftPane draft={draft} />}
    </SetupGate>
  );
}
```

- [ ] **Step 2: Implement `frontend/src/pages/OptimizePage.tsx`**

```tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import AdvisorChat from "../components/AdvisorChat";
import RecipeDraftPane from "../components/RecipeDraftPane";
import { useBoxes } from "../hooks/useBoxes";
import {
  RecipeDraft,
  useCreateAdvisorSession,
  useOptimizeRecipe,
} from "../hooks/useAdvisor";
import { useRecipes } from "../hooks/useRecipes";

export default function OptimizePage() {
  const [params] = useSearchParams();
  const recipes = useRecipes();
  const boxes = useBoxes();
  const [recipe, setRecipe] = useState(params.get("recipe") ?? "");
  const [boxId, setBoxId] = useState("");
  const [goals, setGoals] = useState("throughput");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const opt = useOptimizeRecipe();
  const busy = create.isPending || opt.isPending;
  return (
    <div>
      <h1>Optimize recipe</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
          <option value="">-- recipe --</option>
          {(recipes.data ?? []).map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
          <option value="">-- box --</option>
          {(boxes.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          value={goals}
          onChange={(e) => setGoals(e.target.value)}
          placeholder="comma-separated goals"
        />
        <button
          disabled={!recipe || !boxId || busy}
          onClick={async () => {
            setText("");
            setDraft(null);
            const r = await create.mutateAsync({
              kind: "optimize",
              target_box_id: boxId,
              target_recipe_name: recipe,
            });
            const out = await opt.mutateAsync({
              sid: r.id,
              goals: goals
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            });
            setText(out.text);
            setDraft(out.draft);
          }}
        >
          optimize
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <RecipeDraftPane draft={draft} />}
    </div>
  );
}
```

- [ ] **Step 3: Implement `frontend/src/pages/ModsPage.tsx`**

```tsx
import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import ModDraftPane from "../components/ModDraftPane";
import {
  ModDraft,
  useCreateAdvisorSession,
  useProposeMod,
} from "../hooks/useAdvisor";
import { useDeleteMod, useMods } from "../hooks/useMods";

export default function ModsPage() {
  const mods = useMods();
  const del = useDeleteMod();
  const create = useCreateAdvisorSession();
  const propose = useProposeMod();
  const [hfId, setHfId] = useState("");
  const [errLog, setErrLog] = useState("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<ModDraft | null>(null);
  const busy = create.isPending || propose.isPending;
  return (
    <div>
      <h1>Mods</h1>
      <h2>Existing</h2>
      <ul>
        {(mods.data ?? []).map((m) => (
          <li key={m.name}>
            <code>{m.name}</code> — {m.description}{" "}
            <button onClick={() => del.mutate(m.name)}>delete</button>
          </li>
        ))}
      </ul>
      <h2>Propose new mod (AI)</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <input
          placeholder="huggingface/model-id"
          value={hfId}
          onChange={(e) => setHfId(e.target.value)}
          style={{ minWidth: 280 }}
        />
      </div>
      <textarea
        value={errLog}
        onChange={(e) => setErrLog(e.target.value)}
        placeholder="paste error log or failure description"
        style={{ width: "100%", height: 120 }}
      />
      <div style={{ marginTop: 8 }}>
        <button
          disabled={!hfId || !errLog || busy}
          onClick={async () => {
            setText("");
            setDraft(null);
            const r = await create.mutateAsync({
              kind: "mod",
              hf_model_id: hfId,
            });
            const out = await propose.mutateAsync({
              sid: r.id,
              error_log: errLog,
            });
            setText(out.text);
            setDraft(out.draft);
          }}
        >
          propose
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <ModDraftPane draft={draft} />}
    </div>
  );
}
```

- [ ] **Step 4: Modify `frontend/src/App.tsx`**

Replace the body of `App` (keep file-level imports — add the new ones):

```tsx
import { Link, Route, Routes } from "react-router-dom";

import AdvisorPage from "./pages/AdvisorPage";
import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import ModsPage from "./pages/ModsPage";
import OptimizePage from "./pages/OptimizePage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        <Link to="/">Boxes</Link>
        <Link to="/recipes">Recipes</Link>
        <Link to="/launch">Launch</Link>
        <Link to="/status">Status</Link>
        <Link to="/advisor">Advisor</Link>
        <Link to="/optimize">Optimize</Link>
        <Link to="/mods">Mods</Link>
      </nav>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/advisor" element={<AdvisorPage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="/mods" element={<ModsPage />} />
      </Routes>
    </div>
  );
}
```

- [ ] **Step 5: Add an "optimize" link to `RecipesPage`**

Modify `frontend/src/pages/RecipesPage.tsx`. Find the `<li key={r.name}>` row and add a link before the delete button:

```tsx
            <code>{r.name}</code> — {r.model}{" "}
            <a href={`/optimize?recipe=${encodeURIComponent(r.name)}`}>optimize</a>{" "}
            <button onClick={() => del.mutate(r.name)}>delete</button>
```

- [ ] **Step 6: Build the frontend**

```bash
cd /Users/mchenetz/git/sparkd/frontend && npm run build
```

Expected: build succeeds. Output goes to `sparkd/static/`.

- [ ] **Step 7: Commit**

```bash
cd /Users/mchenetz/git/sparkd
git add frontend/src/pages/AdvisorPage.tsx frontend/src/pages/OptimizePage.tsx frontend/src/pages/ModsPage.tsx frontend/src/App.tsx frontend/src/pages/RecipesPage.tsx sparkd/static
git commit -m "feat(frontend): Advisor, Optimize, Mods pages + recipe optimize link"
```

---

## Task 14: Smoke test the full stack with a fake Anthropic adapter

**Files:**
- Create: `tests/integration/test_full_stack_ai.py`

This task verifies the wiring of all AI features end-to-end without calling the real Anthropic API.

- [ ] **Step 1: Write the test**

`tests/integration/test_full_stack_ai.py`:

```python
"""End-to-end coverage of HF + advisor + mods using a fake AdvisorPort."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from sparkd.advisor import AdvisorChunk
from sparkd.app import build_app
from sparkd.db.engine import init_engine


class FakePort:
    def __init__(self, recipe_text: str, mod_text: str) -> None:
        self.recipe_text = recipe_text
        self.mod_text = mod_text

    async def _yield(self, text: str) -> AsyncIterator[AdvisorChunk]:
        for ch in text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(delta="", input_tokens=10, output_tokens=20, final=True)

    async def stream_recipe(self, info, caps, history):
        async for c in self._yield(self.recipe_text):
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield(self.recipe_text):
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield(self.mod_text):
            yield c


@pytest.fixture
async def client(sparkd_home, monkeypatch):
    await init_engine(create_all=True)
    app = build_app()
    recipe_text = (
        '```json\n{"name":"llama-8b","model":"meta-llama/Llama-3.1-8B-Instruct",'
        '"args":{"--tensor-parallel-size":"2"},"env":{},'
        '"description":"d","rationale":"r"}\n```'
    )
    mod_text = (
        '```json\n{"name":"fix-vocab","target_models":["llama"],'
        '"files":{"patch.diff":"--- a\\n+++ b\\n"},'
        '"description":"d","rationale":"r"}\n```'
    )
    app.state.advisor.port = FakePort(recipe_text, mod_text)
    # stub box capabilities so the advisor can run without a real box
    from datetime import datetime, timezone

    from sparkd.schemas.box import BoxCapabilities

    async def fake_caps(_self, _box_id, *, refresh=False):
        return BoxCapabilities(
            gpu_count=2, gpu_model="NVIDIA GB10", vram_per_gpu_gb=96,
            captured_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(type(app.state.boxes), "capabilities", fake_caps)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await app.state.pool.close_all()


@respx.mock
async def test_full_recipe_flow(client):
    c, _app = client
    respx.get(
        "https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "modelId": "meta-llama/Llama-3.1-8B-Instruct",
                "config": {"architectures": ["LlamaForCausalLM"], "max_position_embeddings": 131072},
                "safetensors": {"total": 16_000_000_000},
            },
        )
    )
    box_id = (
        await c.post("/boxes", json={"name": "b", "host": "h", "user": "u"})
    ).json()["id"]
    sid = (
        await c.post(
            "/advisor/sessions",
            json={
                "kind": "recipe",
                "target_box_id": box_id,
                "hf_model_id": "meta-llama/Llama-3.1-8B-Instruct",
            },
        )
    ).json()["id"]
    r = await c.post(f"/advisor/sessions/{sid}/recipe", json={})
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft["name"] == "llama-8b"
    # accept the draft → save as a recipe
    r = await c.post(
        "/recipes",
        json={
            "name": draft["name"], "model": draft["model"],
            "args": draft["args"], "env": draft["env"], "mods": [],
        },
    )
    assert r.status_code == 201
    # session has tokens
    r = await c.get(f"/advisor/sessions/{sid}")
    assert r.json()["input_tokens"] == 10
    assert r.json()["output_tokens"] == 20


async def test_full_mod_flow(client):
    c, _app = client
    sid = (
        await c.post(
            "/advisor/sessions",
            json={"kind": "mod", "hf_model_id": "meta-llama/x"},
        )
    ).json()["id"]
    r = await c.post(
        f"/advisor/sessions/{sid}/mod",
        json={"error_log": "ImportError: foo"},
    )
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft["name"] == "fix-vocab"
    r = await c.post(
        "/mods",
        json={
            "name": draft["name"],
            "target_models": draft["target_models"],
            "description": draft["description"],
            "files": draft["files"],
            "enabled": True,
        },
    )
    assert r.status_code == 201
    r = await c.get("/mods")
    assert any(m["name"] == "fix-vocab" for m in r.json())
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_full_stack_ai.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass (Plan 1's 63 + new tests from this plan).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_full_stack_ai.py
git commit -m "test: end-to-end AI flow (recipe + mod) with fake AdvisorPort"
```

---

## Self-review

- **Spec coverage** (sections from `docs/superpowers/specs/2026-04-25-sparkd-dashboard-design.md`):
  - `AdvisorService` (§3): Tasks 4 + 5 (port + service); routes Task 9 + 10. Three operations covered: `generate_recipe`, `optimize_recipe`, `propose_mod`.
  - `HFCatalogService` (§3): Task 3.
  - `ModService` (§3, deferred to Plan 2 in original spec scope): Tasks 6 + 8.
  - Pluggable advisor port: Task 4 (`AdvisorPort` Protocol).
  - Anthropic adapter shipped in v1: Task 4.
  - Sessions persisted in SQLite: Task 2.
  - Prompt caching: Task 4 (`cache_control` on the system prompt).
  - Streaming tokens to client: Task 9 (`/ws/advisor/{session}` + REST that aggregates).
  - Frontend advisor + mod UI: Tasks 11–13.
- **API surface coverage** (§5 of spec):
  - `POST /advisor/sessions` ✓ (Task 9), `POST /advisor/sessions/{id}/recipe` ✓ (9), `/optimize` ✓ (9), `/mod` ✓ (9), `GET /advisor/sessions/{id}` ✓ (9). `POST /advisor/sessions/{id}/message` (the explicit "follow-up" REST entry) — covered by `AdvisorService.followup` (Task 5) but no dedicated route added because the streaming WS path (Task 9) is the primary follow-up channel; flagged as a deliberate scope cut consistent with the spec's intent.
  - `GET /mods` ✓ (8), `POST /mods` ✓ (8), `GET/PUT/DELETE /mods/{name}` ✓ (8).
  - `GET /hf/models/{id}` ✓ (7). `GET /hf/models?q=` (search proxy) — not implemented; HF doesn't expose an unauthenticated search endpoint suitable for proxying. Listed as a follow-up.
- **Placeholder scan:** Every code step contains complete code; no "TBD"/"add error handling"/"similar to Task N" patterns.
- **Type consistency:** `RecipeDraft` shape (name, model, args, env, description, rationale) consistent across schemas (Task 1), prompts/parser (Task 4), service (Task 5), routes (Task 9), and frontend hook (Task 11). `ModDraft` likewise. `AdvisorChunk` consistent between adapter (Task 4) and service consumer (Task 5). `AdvisorPort` Protocol methods (`stream_recipe`, `stream_optimize`, `stream_mod`) consistent across adapter, fake ports in tests, and service.
- **Sequencing.** Tasks 0–6 are backend with no frontend. Tasks 7–10 wire backend routes. Tasks 11–13 are frontend. Task 14 is integration smoke. Each task only depends on prior tasks.

No issues found that require fixing inline.
