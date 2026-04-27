# Cluster-as-Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a cluster (a tagged group of boxes) selectable anywhere a single box is selectable, and make multi-node launches actually run end-to-end by delegating orchestration to upstream `run-recipe.sh -n …`.

**Architecture:** A shared `resolve_target()` helper turns a string of the form `"<box_id>"` or `"cluster:<name>"` into a `ResolvedTarget` (head box + members). `LaunchService` uses it to either run `./run-recipe.sh <recipe>` (single-box, today's path) or `./run-recipe.sh -n <head_host>,<worker_host>,... <recipe>` on the head node (cluster path — upstream `launch-cluster.sh` then scps the launch script to workers and bootstraps Ray). On the frontend, two new shared components — `<TargetSelect>` (optgrouped clusters/boxes selector) and `<ChipInput>` (autocomplete-backed pill) — replace ad-hoc inputs everywhere.

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2 async + alembic on the backend; React 18 + Vite + TypeScript + TanStack Query on the frontend.

**Spec:** `docs/superpowers/specs/2026-04-26-cluster-as-target-design.md`

---

## File Structure

**Backend new**
- `sparkd/services/targets.py` — `ResolvedTarget`, `resolve_target()`, `CLUSTER_PREFIX`
- `sparkd/db/migrations/versions/0004_launch_cluster_name.py` — adds nullable `cluster_name` column

**Backend modified**
- `sparkd/schemas/launch.py` — `LaunchCreate.box_id` → `target`; `LaunchRecord` adds `cluster_name`
- `sparkd/db/models.py` — `Launch.cluster_name: str | None`
- `sparkd/services/launch.py` — call `resolve_target`, build `-n` flag for clusters, populate `cluster_name`
- `sparkd/routes/launches.py` — body uses `target`, query filter renamed to `?target=`
- `sparkd/routes/advisor.py` — replace `_resolve_caps`/`_resolve_cluster` with shared resolver

**Frontend new**
- `frontend/src/components/TargetSelect.tsx` — optgrouped clusters + boxes selector
- `frontend/src/components/ChipInput.tsx` — single-value autocomplete chip input

**Frontend modified**
- `frontend/src/pages/AdvisorPage.tsx` — use `<TargetSelect>`
- `frontend/src/pages/OptimizePage.tsx` — use `<TargetSelect>`
- `frontend/src/pages/LaunchPage.tsx` — use `<TargetSelect>`; rename request key `box_id` → `target`
- `frontend/src/pages/BoxesPage.tsx` — remove "advise multi-node" button
- `frontend/src/pages/BoxDetailPage.tsx` — replace cluster `<input>` with `<ChipInput>`
- `frontend/src/components/RecipeAIAssist.tsx` — add `<TargetSelect>` to both inner forms
- `frontend/src/hooks/useLaunches.ts` — `box_id` → `target`; query `?box=` → `?target=`

**Tests**
- `tests/unit/test_targets.py` — new
- `tests/integration/test_launch_service.py` — extend with cluster `-n` assertion
- `tests/integration/test_launch_routes.py` — switch to `target`, add cluster route test
- `tests/integration/test_launch_actions.py` — update `box_id` → `target`
- `tests/integration/test_clusters_routes.py` — unchanged
- `tests/integration/test_advisor_routes.py` — unchanged behaviorally

---

## Task 1: `resolve_target` helper (TDD, pure logic)

**Files:**
- Create: `sparkd/services/targets.py`
- Test: `tests/unit/test_targets.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_targets.py`:

```python
"""Resolve a string `target` (box id or `cluster:<name>`) to a head box +
member list. Pure logic; no SSH, no DB."""

from __future__ import annotations

import pytest

from sparkd.errors import NotFoundError
from sparkd.schemas.box import BoxSpec
from sparkd.services.targets import (
    CLUSTER_PREFIX,
    ResolvedTarget,
    resolve_target,
)


def _box(name: str, host: str, *, cluster: str | None = None) -> BoxSpec:
    return BoxSpec(
        id=f"id-{name}",
        name=name,
        host=host,
        port=22,
        user="u",
        repo_path="~/spark-vllm-docker",
        tags={"cluster": cluster} if cluster else {},
    )


class FakeBoxes:
    def __init__(self, boxes: list[BoxSpec]) -> None:
        self._boxes = {b.id: b for b in boxes}

    async def get(self, box_id: str) -> BoxSpec:
        if box_id not in self._boxes:
            raise NotFoundError("box", box_id)
        return self._boxes[box_id]

    async def list_clusters(self) -> dict[str, list[BoxSpec]]:
        out: dict[str, list[BoxSpec]] = {}
        for b in self._boxes.values():
            name = b.tags.get("cluster")
            if name:
                out.setdefault(name, []).append(b)
        return out


async def test_resolve_none_target_raises():
    boxes = FakeBoxes([])
    with pytest.raises(ValueError):
        await resolve_target(None, boxes)  # type: ignore[arg-type]


async def test_resolve_single_box_target():
    a = _box("a", "10.0.0.1")
    boxes = FakeBoxes([a])
    r = await resolve_target(a.id, boxes)  # type: ignore[arg-type]
    assert r.kind == "box"
    assert r.head_box.id == a.id
    assert [m.id for m in r.members] == [a.id]
    assert r.cluster_name is None


async def test_resolve_unknown_box_raises():
    boxes = FakeBoxes([])
    with pytest.raises(NotFoundError):
        await resolve_target("ghost", boxes)  # type: ignore[arg-type]


async def test_resolve_cluster_target():
    n1 = _box("n1", "10.0.0.1", cluster="alpha")
    n2 = _box("n2", "10.0.0.2", cluster="alpha")
    n3 = _box("n3", "10.0.0.3", cluster="alpha")
    other = _box("solo", "10.0.0.99")
    boxes = FakeBoxes([n1, n2, n3, other])
    r = await resolve_target(f"{CLUSTER_PREFIX}alpha", boxes)  # type: ignore[arg-type]
    assert r.kind == "cluster"
    assert r.cluster_name == "alpha"
    assert r.head_box.id == n1.id  # first member is head
    assert [m.id for m in r.members] == [n1.id, n2.id, n3.id]


async def test_resolve_unknown_cluster_raises():
    boxes = FakeBoxes([_box("a", "10.0.0.1")])
    with pytest.raises(NotFoundError):
        await resolve_target(f"{CLUSTER_PREFIX}nope", boxes)  # type: ignore[arg-type]


async def test_resolve_empty_cluster_raises():
    """A cluster name was registered (somehow) but has no members. Treat as missing."""
    boxes = FakeBoxes([])  # list_clusters returns {} → "alpha" missing
    with pytest.raises(NotFoundError):
        await resolve_target(f"{CLUSTER_PREFIX}alpha", boxes)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/unit/test_targets.py -v`
Expected: ImportError or "module sparkd.services.targets has no attribute …" — module doesn't exist yet.

- [ ] **Step 3: Implement `targets.py`**

Create `sparkd/services/targets.py`:

```python
"""Resolve a `target` string ("<box_id>" | "cluster:<name>") to a head box
and member list. Used by LaunchService, AdvisorService, and OptimizeService
so the cluster-as-target convention has exactly one implementation.

The CLUSTER_PREFIX is exported here as the canonical source; legacy uses
elsewhere should import from this module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from sparkd.errors import NotFoundError
from sparkd.schemas.box import BoxSpec

CLUSTER_PREFIX = "cluster:"


@dataclass
class ResolvedTarget:
    kind: Literal["box", "cluster"]
    head_box: BoxSpec        # SSH lands here
    members: list[BoxSpec]   # [head] for single-box; all members for cluster
    cluster_name: str | None


class _BoxesLike(Protocol):
    async def get(self, box_id: str) -> BoxSpec: ...
    async def list_clusters(self) -> dict[str, list[BoxSpec]]: ...


async def resolve_target(target: str, boxes: _BoxesLike) -> ResolvedTarget:
    """Resolve a target string to a ResolvedTarget.

    - "<box_id>" → kind="box", head=that box, members=[that box]
    - "cluster:<name>" → kind="cluster", head=first member, members=all
    - anything falsy → ValueError (callers must pre-validate)
    - unknown box id or unknown cluster name → NotFoundError
    - cluster name with zero members → NotFoundError
    """
    if not target:
        raise ValueError("target is required")
    if target.startswith(CLUSTER_PREFIX):
        name = target[len(CLUSTER_PREFIX):]
        grouped = await boxes.list_clusters()
        members = grouped.get(name) or []
        if not members:
            raise NotFoundError("cluster", name)
        return ResolvedTarget(
            kind="cluster",
            head_box=members[0],
            members=list(members),
            cluster_name=name,
        )
    box = await boxes.get(target)  # raises NotFoundError on miss
    return ResolvedTarget(
        kind="box", head_box=box, members=[box], cluster_name=None
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/unit/test_targets.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add sparkd/services/targets.py tests/unit/test_targets.py
git commit -m "feat(targets): shared resolve_target() for box-or-cluster strings"
```

---

## Task 2: Add `cluster_name` column on launches (DB + alembic)

**Files:**
- Modify: `sparkd/db/models.py:Launch`
- Create: `sparkd/db/migrations/versions/0004_launch_cluster_name.py`

- [ ] **Step 1: Add the column to the ORM model**

In `sparkd/db/models.py`, locate `class Launch(Base):` and add a `cluster_name` column right after `box_id`:

```python
class Launch(Base):
    __tablename__ = "launches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    box_id: Mapped[str] = mapped_column(ForeignKey("boxes.id"))
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)
    recipe_name: Mapped[str] = mapped_column(String)
    # …rest unchanged
```

- [ ] **Step 2: Write the alembic migration**

Create `sparkd/db/migrations/versions/0004_launch_cluster_name.py`:

```python
"""launch cluster_name

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "launches",
        sa.Column("cluster_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("launches", "cluster_name")
```

- [ ] **Step 3: Verify the model still loads cleanly**

Run: `cd /Users/mchenetz/git/sparkd && uv run python -c "from sparkd.db.models import Launch; print(Launch.__table__.columns.keys())"`
Expected: a list including `cluster_name`.

- [ ] **Step 4: Run the existing test suite**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest -q`
Expected: still 162 passed (1 new from Task 1 + 161 existing). The new column is nullable so no existing test breaks.

- [ ] **Step 5: Commit**

```bash
git add sparkd/db/models.py sparkd/db/migrations/versions/0004_launch_cluster_name.py
git commit -m "feat(db): add nullable cluster_name to launches"
```

---

## Task 3: `LaunchCreate.target` + `LaunchRecord.cluster_name`

**Files:**
- Modify: `sparkd/schemas/launch.py`

- [ ] **Step 1: Update the schemas**

Replace the contents of `sparkd/schemas/launch.py` with:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LaunchState(str, Enum):
    starting = "starting"
    healthy = "healthy"
    paused = "paused"
    failed = "failed"
    stopped = "stopped"
    interrupted = "interrupted"


ACTIVE_STATES = frozenset({"starting", "healthy", "paused"})


class LaunchCreate(BaseModel):
    recipe: str = Field(min_length=1)
    target: str = Field(min_length=1)  # box id, or "cluster:<name>"
    mods: list[str] = Field(default_factory=list)
    overrides: dict[str, str] = Field(default_factory=dict)


class LaunchRecord(BaseModel):
    id: str
    box_id: str  # head box for cluster launches; SSH-anchored
    cluster_name: str | None = None  # populated for cluster targets
    recipe_name: str
    state: LaunchState
    container_id: str | None
    command: str
    log_path: str | None = None
    started_at: datetime
    stopped_at: datetime | None
    exit_info: dict[str, Any] | None
```

- [ ] **Step 2: Run tests to identify the breakage surface**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest -q 2>&1 | tail -40`
Expected: failures in `test_launch_service.py`, `test_launch_routes.py`, `test_launch_actions.py` complaining that `box_id` is missing or `target` is required. This is the breakage surface we'll fix in Tasks 4–5.

- [ ] **Step 3: Commit (broken — fixed in Task 4)**

```bash
git add sparkd/schemas/launch.py
git commit -m "refactor(schemas): LaunchCreate.box_id -> target, LaunchRecord adds cluster_name"
```

---

## Task 4: Wire `LaunchService` to `resolve_target` + cluster `-n` flag

**Files:**
- Modify: `sparkd/services/launch.py`
- Modify: `tests/integration/test_launch_service.py`

- [ ] **Step 1: Add a cluster-launch test (will fail; drives the impl)**

In `tests/integration/test_launch_service.py`, after `test_launch_records_starting_state`, add:

```python
async def test_cluster_launch_uses_dash_n_flag(env, monkeypatch):
    """A cluster target invokes ./run-recipe.sh with -n <head>,<worker>,... on the head box."""
    ls, box_svc, lib, fake, _ = env
    fake.set_default(stdout="12345\n", exit=0)
    head = await box_svc.create(
        BoxCreate(name="n1", host="10.0.0.1", user="u", tags={"cluster": "alpha"})
    )
    worker1 = await box_svc.create(
        BoxCreate(name="n2", host="10.0.0.2", user="u", tags={"cluster": "alpha"})
    )
    worker2 = await box_svc.create(
        BoxCreate(name="n3", host="10.0.0.3", user="u", tags={"cluster": "alpha"})
    )
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    rec = await ls.launch(LaunchCreate(recipe="r1", target="cluster:alpha"))
    assert rec.box_id == head.id
    assert rec.cluster_name == "alpha"
    # Exactly one SSH command on the head; must contain -n <ips>.
    assert any(
        "./run-recipe.sh -n 10.0.0.1,10.0.0.2,10.0.0.3 r1" in c
        for c in fake.received
    ), f"expected -n flag in head command; got {fake.received}"
    # Workers receive nothing — upstream launch-cluster.sh does the fan-out.
    _ = (worker1, worker2)
```

- [ ] **Step 2: Update existing single-box tests to use `target`**

In the same file, change every `LaunchCreate(recipe="r1", box_id=bs.id)` to `LaunchCreate(recipe="r1", target=bs.id)`. Use a single-pass find/replace; there should be 3 such call sites (`test_launch_records_starting_state`, `test_launch_persists_log_path`, `test_stop_kills_container`).

Also, add this assertion to `test_launch_records_starting_state` so the regression is locked:

```python
    # Single-box path must NOT inject -n.
    assert not any("-n " in c and "./run-recipe.sh" in c for c in fake.received)
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/integration/test_launch_service.py::test_cluster_launch_uses_dash_n_flag -v`
Expected: FAIL — `LaunchCreate(target=...)` raises a validation error from the schema, OR `LaunchService.launch` looks for `body.box_id` and crashes.

- [ ] **Step 4: Update `LaunchService.launch` and `_to_record`**

In `sparkd/services/launch.py`:

Replace the top-level `_to_record` with:

```python
def _to_record(row: Launch) -> LaunchRecord:
    return LaunchRecord(
        id=row.id,
        box_id=row.box_id,
        cluster_name=row.cluster_name,
        recipe_name=row.recipe_name,
        state=LaunchState(row.state),
        container_id=row.container_id,
        command=row.command,
        log_path=row.log_path,
        started_at=row.started_at,
        stopped_at=row.stopped_at,
        exit_info=row.exit_info_json,
    )
```

Add the import at the top of the file:

```python
from sparkd.services.targets import resolve_target
```

Replace the `async def launch(self, body: LaunchCreate) -> LaunchRecord:` body (everything inside the method) with:

```python
    async def launch(self, body: LaunchCreate) -> LaunchRecord:
        resolved = await resolve_target(body.target, self.boxes)
        head_id = resolved.head_box.id
        recipe = self.library.load_recipe(body.recipe, box_id=head_id)
        issues = await self.recipes.validate(recipe, head_id)
        if issues:
            raise ValidationError(
                "recipe failed pre-flight validation",
                details={"issues": issues},
            )
        try:
            raw_yaml = self.library.load_recipe_text(body.recipe, box_id=head_id)
            raw_recipe = yaml.safe_load(raw_yaml) or {}
        except Exception:  # noqa: BLE001
            raw_recipe = {}
        container_image = (raw_recipe.get("container") or "vllm-node").strip()
        await self._sync_files(body.recipe, head_id, body.mods)
        launch_id = uuid.uuid4().hex[:12]
        log_path = f"~/.sparkd-launches/{launch_id}.log"
        async with session_scope() as s:
            box_row = await s.get(Box, head_id)
            if box_row is None:
                raise NotFoundError("box", head_id)
            target = self.boxes._target_for(box_row)
            # Single-box: ./run-recipe.sh r1
            # Cluster:    ./run-recipe.sh -n h1,h2,h3 r1
            #   Upstream run-recipe.py invokes launch-cluster.sh with that
            #   list; launch-cluster.sh scps to workers and bootstraps Ray.
            if resolved.kind == "cluster":
                node_csv = ",".join(b.host for b in resolved.members)
                run_cmd = f"./run-recipe.sh -n {node_csv} {body.recipe}"
            else:
                run_cmd = f"./run-recipe.sh {body.recipe}"
            cmd = (
                f"mkdir -p ~/.sparkd-launches && "
                f"( nohup bash -lc 'cd {box_row.repo_path} "
                f"&& yes | {run_cmd}' "
                f"> {log_path} 2>&1 < /dev/null & ) ; echo $!"
            )
        result = await self.pool.run(target, cmd)
        if result.exit_status not in (0, None):
            raise ConflictError(f"failed to start: {result.stderr.strip()}")
        snapshot = recipe.model_dump()
        snapshot["container"] = container_image
        async with session_scope() as s:
            row = Launch(
                id=launch_id,
                box_id=head_id,
                cluster_name=resolved.cluster_name,
                recipe_name=body.recipe,
                recipe_snapshot_json=snapshot,
                mods_json=body.mods,
                state=LaunchState.starting.value,
                log_path=log_path,
                container_id=None,
                command=cmd,
            )
            s.add(row)
            await s.flush()
            return _to_record(row)
```

- [ ] **Step 5: Run launch-service tests**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/integration/test_launch_service.py -v`
Expected: 4 passed (3 existing renamed + 1 new cluster test).

- [ ] **Step 6: Commit**

```bash
git add sparkd/services/launch.py tests/integration/test_launch_service.py
git commit -m "feat(launch): cluster targets invoke run-recipe.sh -n on the head box"
```

---

## Task 5: Update launch routes and the `useLaunches` hook contract

**Files:**
- Modify: `sparkd/routes/launches.py`
- Modify: `tests/integration/test_launch_routes.py`
- Modify: `tests/integration/test_launch_actions.py`

- [ ] **Step 1: Update the route handlers**

In `sparkd/routes/launches.py`, accept `target` (instead of `box`) on the listing endpoint and resolve cluster-scoped listings via the shared resolver. Add the necessary imports at the top of the file:

```python
from sparkd.services.box import BoxService
from sparkd.services.targets import resolve_target
```

Add a small dependency for `BoxService`:

```python
def _boxes(request: Request) -> BoxService:
    return request.app.state.boxes
```

Replace the existing `list_launches` handler with:

```python
@router.get("", response_model=list[LaunchRecord])
async def list_launches(
    target: str | None = None,
    active: bool = False,
    ls: LaunchService = Depends(_ls),
    boxes: BoxService = Depends(_boxes),
) -> list[LaunchRecord]:
    """Filter launches by target. Single-box target → query directly. Cluster
    target → union of launches across all member boxes."""
    if target and target.startswith("cluster:"):
        resolved = await resolve_target(target, boxes)
        out: list[LaunchRecord] = []
        for m in resolved.members:
            out.extend(await ls.list(box_id=m.id, active_only=active))
        return out
    return await ls.list(box_id=target, active_only=active)
```

(`LaunchService.list` keeps the internal `box_id=` kwarg — DB rows store the head box id, so the actual lookup is unchanged.)

- [ ] **Step 2: Update existing route tests**

In `tests/integration/test_launch_routes.py`, replace the launch creation call with:

```python
    r = await client.post("/api/launches", json={"recipe": "r1", "target": bid})
```

In `tests/integration/test_launch_actions.py`, find every place that posts to `/api/launches` with a `"box_id"` key and rename to `"target"`. Likewise any `?box=` query parameter becomes `?target=`. (Run `grep -n "box_id\|?box=" tests/integration/test_launch*` first to enumerate.)

- [ ] **Step 3: Add a route-level cluster test**

At the end of `tests/integration/test_launch_routes.py`:

```python
async def test_launch_route_accepts_cluster_target(env):
    client, _app, _box = env
    h = (
        await client.post(
            "/api/boxes",
            json={"name": "n1", "host": "10.0.0.1", "user": "u",
                  "tags": {"cluster": "alpha"}},
        )
    ).json()
    await client.post(
        "/api/boxes",
        json={"name": "n2", "host": "10.0.0.2", "user": "u",
              "tags": {"cluster": "alpha"}},
    )
    await client.post("/api/recipes", json={"name": "r1", "model": "m"})
    r = await client.post(
        "/api/launches", json={"recipe": "r1", "target": "cluster:alpha"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["box_id"] == h["id"]
    assert body["cluster_name"] == "alpha"
```

- [ ] **Step 4: Run launch tests**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/integration/test_launch_routes.py tests/integration/test_launch_actions.py -v`
Expected: all pass.

- [ ] **Step 5: Run full suite**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest -q`
Expected: all pass (162 + cluster route test = 163).

- [ ] **Step 6: Commit**

```bash
git add sparkd/routes/launches.py tests/integration/test_launch_routes.py tests/integration/test_launch_actions.py
git commit -m "feat(launch routes): /launches accepts target= (box id or cluster:<name>)"
```

---

## Task 6: Refactor `routes/advisor.py` to use shared resolver

**Files:**
- Modify: `sparkd/routes/advisor.py`

- [ ] **Step 1: Replace `_resolve_caps` and `_resolve_cluster`**

In `sparkd/routes/advisor.py`, delete the local `CLUSTER_PREFIX` constant and the `_resolve_caps` + `_resolve_cluster` helper functions. Import the shared resolver:

```python
from sparkd.services.targets import CLUSTER_PREFIX, resolve_target
```

Add two new helpers in their place that build on `resolve_target`:

```python
async def _resolve_caps(
    target_box_id: str | None, boxes: BoxService
) -> BoxCapabilities:
    """Capabilities of the head box, falling back to canonical defaults."""
    if not target_box_id:
        return default_dgx_spark_caps()
    try:
        resolved = await resolve_target(target_box_id, boxes)
        return await boxes.capabilities(resolved.head_box.id)
    except Exception:  # noqa: BLE001  — degrade gracefully
        return default_dgx_spark_caps()


async def _resolve_cluster(
    target_box_id: str | None, boxes: BoxService
) -> dict | None:
    """Topology dict for cluster targets; None for single-box / unset."""
    if not target_box_id or not target_box_id.startswith(CLUSTER_PREFIX):
        return None
    try:
        resolved = await resolve_target(target_box_id, boxes)
    except Exception:  # noqa: BLE001
        return None
    if resolved.kind != "cluster":
        return None
    nodes: list[dict] = []
    for box in resolved.members:
        try:
            caps = await boxes.capabilities(box.id)
        except Exception:  # noqa: BLE001
            caps = default_dgx_spark_caps()
        nodes.append(
            {
                "name": box.name,
                "host": box.host,
                "gpu_count": caps.gpu_count,
                "gpu_model": caps.gpu_model,
                "vram_gb": caps.vram_per_gpu_gb,
                "ib": caps.ib_interface,
            }
        )
    total_gpus = sum(n["gpu_count"] for n in nodes)
    total_vram = sum(n["gpu_count"] * n["vram_gb"] for n in nodes)
    return {
        "name": resolved.cluster_name,
        "nodes": nodes,
        "total_gpus": total_gpus,
        "total_vram_gb": total_vram,
    }
```

- [ ] **Step 2: Run advisor + cluster tests**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest tests/integration/test_advisor_routes.py tests/integration/test_clusters_routes.py -v`
Expected: all pass — behavior unchanged, just delegated through the shared resolver.

- [ ] **Step 3: Run full suite**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest -q`
Expected: all pass (≥163).

- [ ] **Step 4: Commit**

```bash
git add sparkd/routes/advisor.py
git commit -m "refactor(advisor): route resolves through shared resolve_target helper"
```

---

## Task 7: `<ChipInput>` component (frontend)

**Files:**
- Create: `frontend/src/components/ChipInput.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ChipInput.tsx`:

```tsx
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Pill } from "./Card";

type Props = {
  /** Current value. "" means no chip is set. */
  value: string;
  /** Called with the new value. "" to clear. */
  onChange: (next: string) => void;
  /** Existing values to autocomplete from. */
  suggestions: string[];
  placeholder?: string;
  /** Visual tone for the chip pill. Default "info". */
  chipTone?: "info" | "neutral";
};

/**
 * Single-value chip input with autocomplete. Type to filter `suggestions`,
 * Tab/Enter to commit (selected suggestion or typed novel value), and the
 * input is replaced with a removable pill. Click the pill to edit.
 *
 * Why custom (vs. a third-party tag-input lib): keeps the bundle small and
 * matches the project's hand-rolled aesthetic — `Pill` token, monospace,
 * no extra dependencies.
 */
export default function ChipInput({
  value,
  onChange,
  suggestions,
  placeholder,
  chipTone = "info",
}: Props) {
  const [editing, setEditing] = useState(value === "");
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(value);
    setEditing(value === "");
  }, [value]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const filtered = suggestions
    .filter((s) => s.toLowerCase().includes(draft.toLowerCase()))
    .slice(0, 8);
  const exactMatch = suggestions.includes(draft);

  function commit(next: string) {
    onChange(next);
    setEditing(false);
    setOpen(false);
  }

  function clear() {
    onChange("");
    setDraft("");
    setEditing(true);
  }

  if (!editing && value) {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <button
          type="button"
          onClick={() => setEditing(true)}
          style={{
            background: "transparent",
            border: "none",
            padding: 0,
            cursor: "text",
          }}
          aria-label={`edit ${value}`}
        >
          <Pill tone={chipTone}>
            {value}
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                clear();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  clear();
                }
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                marginLeft: 4,
                cursor: "pointer",
              }}
              aria-label={`remove ${value}`}
            >
              <X size={11} />
            </span>
          </Pill>
        </button>
      </span>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        ref={inputRef}
        className="mono"
        value={draft}
        placeholder={placeholder}
        onChange={(e) => {
          setDraft(e.target.value);
          setOpen(true);
          setHighlight(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === "Tab") {
            const picked =
              open && filtered.length > 0 && filtered[highlight] !== undefined
                ? filtered[highlight]
                : draft.trim();
            if (picked) {
              e.preventDefault();
              commit(picked);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlight((h) => Math.min(h + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((h) => Math.max(h - 1, 0));
          }
        }}
      />
      {open && (filtered.length > 0 || (draft && !exactMatch)) && (
        <ul
          role="listbox"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 20,
            margin: "2px 0 0",
            padding: 4,
            listStyle: "none",
            background: "var(--bg-elev-2)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {filtered.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={i === highlight}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(s);
              }}
              onMouseEnter={() => setHighlight(i)}
              style={{
                padding: "4px 8px",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                background:
                  i === highlight ? "var(--bg-overlay)" : "transparent",
                borderRadius: 4,
              }}
            >
              {s}
            </li>
          ))}
          {draft && !exactMatch && (
            <li
              role="option"
              aria-selected={false}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(draft.trim());
              }}
              style={{
                padding: "4px 8px",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--fg-muted)",
                borderTop:
                  filtered.length > 0
                    ? "1px solid var(--border-subtle)"
                    : "none",
                marginTop: filtered.length > 0 ? 4 : 0,
                paddingTop: filtered.length > 0 ? 6 : 4,
              }}
            >
              ↵ create &ldquo;{draft.trim()}&rdquo;
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: `built in <Xms>` with no TypeScript errors. Component is unused for now (added in Task 8).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChipInput.tsx
git commit -m "feat(ui): ChipInput — single-value autocomplete pill"
```

---

## Task 8: Use `<ChipInput>` for the cluster field on `BoxDetailPage`

**Files:**
- Modify: `frontend/src/pages/BoxDetailPage.tsx`

- [ ] **Step 1: Wire `useClusters()` and replace the cluster field**

At the top of `BoxDetailPage.tsx`, add the imports:

```tsx
import ChipInput from "../components/ChipInput";
import { useClusters } from "../hooks/useClusters";
```

Inside the component (alongside existing hook calls), add:

```tsx
const clusters = useClusters();
const knownClusters = (clusters.data?.clusters ?? []).map((c) => c.name);
```

Replace the existing cluster `<Field>` (around lines 192-207) with:

```tsx
<Field
  label="cluster"
  hint="boxes sharing a cluster name form a multi-node group"
>
  <ChipInput
    value={draft.tags?.cluster ?? ""}
    onChange={(next) => {
      const tags = { ...(draft.tags ?? {}) };
      if (next) tags.cluster = next;
      else delete tags.cluster;
      setField("tags", tags);
    }}
    suggestions={knownClusters}
    placeholder="alpha"
  />
</Field>
```

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: `built in <Xms>` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/BoxDetailPage.tsx
git commit -m "feat(ui): cluster field on box detail uses ChipInput with autocomplete"
```

---

## Task 9: `<TargetSelect>` component (frontend)

**Files:**
- Create: `frontend/src/components/TargetSelect.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/TargetSelect.tsx`:

```tsx
import { useBoxes } from "../hooks/useBoxes";
import { useClusters } from "../hooks/useClusters";

type Props = {
  /** Current value: "", "<box_id>", or "cluster:<name>". */
  value: string;
  onChange: (next: string) => void;
  /** Show the clusters optgroup. Default true. */
  allowClusters?: boolean;
  /** Show a leading "default" option (empty value). Default false. */
  allowDefault?: boolean;
  /** Label for the default option (when allowDefault). */
  defaultLabel?: string;
  /** Placeholder when neither default nor any options apply. */
  placeholder?: string;
};

/**
 * Optgrouped selector for "pick a target". Sole source of truth for the
 * cluster-or-box picker UX. Encodes cluster targets as `cluster:<name>`.
 */
export default function TargetSelect({
  value,
  onChange,
  allowClusters = true,
  allowDefault = false,
  defaultLabel = "DGX Spark (default specs)",
  placeholder = "— target box —",
}: Props) {
  const boxes = useBoxes();
  const clusters = useClusters();
  const clusterList = clusters.data?.clusters ?? [];
  const boxList = boxes.data ?? [];
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowDefault ? (
        <option value="">{defaultLabel}</option>
      ) : (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {allowClusters && clusterList.length > 0 && (
        <optgroup label="clusters (multi-node)">
          {clusterList.map((c) => (
            <option key={c.name} value={`cluster:${c.name}`}>
              {c.name} — {c.box_count} node{c.box_count === 1 ? "" : "s"}
            </option>
          ))}
        </optgroup>
      )}
      {boxList.length > 0 && (
        <optgroup label="single box">
          {boxList.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
              {b.host ? ` · ${b.host}` : ""}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}
```

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds. Component still unused (wired in Tasks 10–13).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TargetSelect.tsx
git commit -m "feat(ui): TargetSelect — shared optgrouped clusters/boxes picker"
```

---

## Task 10: `AdvisorPage` uses `<TargetSelect>`

**Files:**
- Modify: `frontend/src/pages/AdvisorPage.tsx`

- [ ] **Step 1: Replace the inline select**

In `AdvisorPage.tsx`:

- Add the import: `import TargetSelect from "../components/TargetSelect";`
- Remove `import { useBoxes } from "../hooks/useBoxes";` (no longer used directly).
- Remove `const boxes = useBoxes();` line.
- Remove the local `CLUSTER_PREFIX` constant if unused after the change.
- Replace the entire `<select>…</select>` block (currently lines 81–106) with:

```tsx
<TargetSelect
  value={target}
  onChange={setTarget}
  allowDefault
  defaultLabel="DGX Spark (default specs)"
/>
```

The `isCluster` derivation (`target.startsWith(CLUSTER_PREFIX)`) needs to remain. If you removed `CLUSTER_PREFIX`, replace its uses with the literal `"cluster:"` (or keep importing it from `@/services/...`-equivalent — there's no shared TS constant, so the literal is the simplest option):

```tsx
const isCluster = target.startsWith("cluster:");
const activeCluster = isCluster
  ? clusterList.find((c) => c.name === target.slice("cluster:".length))
  : null;
```

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AdvisorPage.tsx
git commit -m "refactor(ui): AdvisorPage uses shared TargetSelect"
```

---

## Task 11: `OptimizePage` uses `<TargetSelect>`

**Files:**
- Modify: `frontend/src/pages/OptimizePage.tsx`

- [ ] **Step 1: Replace the box select**

In `OptimizePage.tsx`:

- Add: `import TargetSelect from "../components/TargetSelect";`
- Remove the `useBoxes` import and the `const boxes = useBoxes();` call.
- Replace the second `<select>` (the one with the `boxes` map, lines 71–78) with:

```tsx
<TargetSelect value={boxId} onChange={setBoxId} allowDefault />
```

The state variable is already named `boxId` and is passed as `target_box_id` to the advisor session, which already accepts `cluster:<name>` — no change needed downstream.

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/OptimizePage.tsx
git commit -m "refactor(ui): OptimizePage uses TargetSelect (clusters allowed)"
```

---

## Task 12: `LaunchPage` uses `<TargetSelect>` + `useLaunches` rename

**Files:**
- Modify: `frontend/src/pages/LaunchPage.tsx`
- Modify: `frontend/src/hooks/useLaunches.ts`

- [ ] **Step 1: Update the launches hook**

In `frontend/src/hooks/useLaunches.ts`, change:

```ts
export function useLaunches(boxId?: string, opts?: { activeOnly?: boolean }) {
  const params = new URLSearchParams();
  if (boxId) params.set("box", boxId);
  // …
```

to:

```ts
export function useLaunches(target?: string, opts?: { activeOnly?: boolean }) {
  const params = new URLSearchParams();
  if (target) params.set("target", target);
  // …
}
```

(also update the `queryKey` first arg from `boxId ?? null` → `target ?? null`).

Also update the `Launch` type to include `cluster_name`:

```ts
export type Launch = {
  id: string;
  box_id: string;
  cluster_name: string | null;
  recipe_name: string;
  // …rest unchanged
};
```

And the `useCreateLaunch` body type:

```ts
mutationFn: (body: { recipe: string; target: string; mods?: string[] }) =>
  api.post<Launch>("/launches", body),
```

- [ ] **Step 2: Update `LaunchPage`**

In `frontend/src/pages/LaunchPage.tsx`:

- Add: `import TargetSelect from "../components/TargetSelect";`
- Remove the `useBoxes` import + the `const { data: boxes } = useBoxes();` call.
- Rename local state: `const [box, setBox] = useState("");` → `const [target, setTarget] = useState("");`
- Replace the box `<select>` (lines 69-76) with:

```tsx
<TargetSelect value={target} onChange={setTarget} placeholder="— target —" />
```

- Change the disabled check & mutate call:

```tsx
disabled={!target || !recipe || create.isPending}
onClick={() => create.mutate({ recipe, target })}
```

- Update the `box=` display badge inside `ActiveLaunch` (line 161) to render the cluster pill when present:

```tsx
import { Network } from "lucide-react";

// …inside ActiveLaunch, after the recipe name span:
{launch.cluster_name ? (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
    <Network size={11} style={{ color: "var(--fg-muted)" }} />
    <Pill tone="info">{launch.cluster_name}</Pill>
  </span>
) : null}
<span
  style={{
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    color: "var(--fg-muted)",
  }}
>
  box={launch.box_id.slice(0, 8)}
</span>
```

- [ ] **Step 3: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LaunchPage.tsx frontend/src/hooks/useLaunches.ts
git commit -m "feat(ui): launch page uses TargetSelect; cluster pill on launch row"
```

---

## Task 13: `RecipeAIAssist` adds `<TargetSelect>`

**Files:**
- Modify: `frontend/src/components/RecipeAIAssist.tsx`

- [ ] **Step 1: Add the picker**

In `RecipeAIAssist.tsx`:

- Add: `import TargetSelect from "./TargetSelect";`
- Add a `target` state next to `goal`:

```tsx
const [target, setTarget] = useState("");
```

- In the "fill from a hugging face model" form (visible when `isNew`), add the `<TargetSelect>` above the existing input row:

```tsx
{isNew && (
  <div style={{ display: "grid", gap: 10, marginBottom: 12 }}>
    <div style={{ /* eyebrow styles unchanged */ }}>
      fill from a hugging face model
    </div>
    <TargetSelect
      value={target}
      onChange={setTarget}
      allowDefault
      defaultLabel="DGX Spark (default specs)"
    />
    <div style={{ display: "flex", gap: 6 }}>
      {/* existing input + fill button */}
    </div>
  </div>
)}
```

- Replace the two hardcoded `target_box_id: null` calls with `target_box_id: target || null` in both `create.mutateAsync` calls (the "fill" path and the "tune" path).

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/RecipeAIAssist.tsx
git commit -m "feat(ui): RecipeAIAssist accepts cluster targets via TargetSelect"
```

---

## Task 14: Remove "advise multi-node" button from `BoxesPage`

**Files:**
- Modify: `frontend/src/pages/BoxesPage.tsx`

- [ ] **Step 1: Delete the CTA block**

In `BoxesPage.tsx`, delete the entire `<div>` containing the "⟶ advise multi-node" button (lines 99-122 in the current file — the block that starts with `marginTop: 10` border-top divider and contains the `Link` to `/advisor?cluster=...`):

```tsx
<div
  style={{
    marginTop: 10,
    paddingTop: 10,
    borderTop: "1px solid var(--border-subtle)",
    display: "flex",
    justifyContent: "flex-end",
  }}
>
  <Link
    to={`/advisor?cluster=${encodeURIComponent(cl.name)}`}
    style={{ borderBottom: "none" }}
  >
    <button className="ghost">
      <span
        style={{
          color: "var(--accent-ai)",
          fontSize: 12,
        }}
      >
        ⟶ advise multi-node
      </span>
    </button>
  </Link>
</div>
```

If `Link` is now only used inside the cluster member list, leave its import in place. Otherwise, leave the import — it's still used by the member-list `Link`s.

- [ ] **Step 2: Verify the frontend builds**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/BoxesPage.tsx
git commit -m "ui(boxes): remove 'advise multi-node' shortcut from cluster cards"
```

---

## Task 15: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `cd /Users/mchenetz/git/sparkd && uv run pytest -q`
Expected: all pass — should be ≥164 (161 baseline + 6 unit + cluster route test, minus zero deletions).

- [ ] **Step 2: Build the frontend**

Run: `cd /Users/mchenetz/git/sparkd/frontend && npm run build 2>&1 | tail -10`
Expected: clean build.

- [ ] **Step 3: Smoke-check the SPA bundle**

Run: `ls -la /Users/mchenetz/git/sparkd/sparkd/static/assets/`
Expected: a fresh `index-*.js` and `index-*.css` from this build.

- [ ] **Step 4: Final tag-up commit (if needed)**

If any task left uncommitted artifacts (e.g., the rebuilt `sparkd/static/`), commit them:

```bash
git status
# If sparkd/static has changes, they're build artifacts — commit them with:
git add sparkd/static
git commit -m "build: rebuild SPA bundle for cluster-as-target"
```

If `git status` is clean, skip this step.

- [ ] **Step 5: Summary check**

Run: `git log --oneline feba790..HEAD`
Expected: a tidy chain of commits implementing the spec — `targets.py`, db migration, schema rename, launch service, launch routes, advisor refactor, ChipInput, BoxDetailPage chip, TargetSelect, AdvisorPage/OptimizePage/LaunchPage refactors, RecipeAIAssist target, BoxesPage cleanup, optional rebuild commit.
