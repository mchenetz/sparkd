# Cluster as a first-class target

**Date:** 2026-04-26
**Status:** Approved (design)

## Summary

Make a cluster (a tagged group of boxes) selectable anywhere a single box is selectable today, and make multi-node launches actually work end-to-end by delegating orchestration to upstream `spark-vllm-docker`.

Today, only the AI Advisor accepts a cluster target; launches and the optimize flow are single-box only. This spec extends the existing `cluster:<name>` target encoding to every box-input surface and wires the launch path so a cluster target invokes `run-recipe.sh -n <ips...>` on the head node — letting upstream `launch-cluster.sh` do the actual multi-node orchestration (scp to workers, Ray bootstrap, NCCL config).

## Goals

- A cluster is a valid target wherever a box is valid: launches, optimize, recipe AI assist, advisor.
- Multi-node launches work: pick a cluster, hit launch, get a running multi-node vLLM serve.
- Recipes generated against a cluster are tuned for multi-node (TP/PP, distributed-executor-backend, NCCL env) — already done by the advisor; no recipe schema change needed.
- Zero new orchestration code in sparkd: rely on upstream `run-recipe.sh -n` for the multi-node fan-out.
- "Advise multi-node" CTA on the Boxes page is removed (clusters are now usable everywhere, so the shortcut is redundant).

## Non-goals

- No `cluster:` block in recipe YAML. Multi-node-ness is purely a launch-time concern. The recipe stays node-agnostic; the AI advisor already tunes `args`/`env` for cluster-sized hardware.
- No per-node status panels. The head node's container is the unit of monitoring; upstream manages workers transparently.
- No tag editor UI changes. The existing `cluster` field on `BoxDetailPage` is sufficient.
- No backward-compat for the old `box_id` launch field. sparkd is pre-release; we rename cleanly.

## Orchestration model (decision)

**A. SSH-to-head, fan-out via run-recipe.sh.** Confirmed during brainstorming. For a cluster target:

- The **head node** is the first member of the cluster (registration order from `BoxService.list_clusters()`).
- sparkd syncs recipe files to the head node only.
- sparkd SSHes to the head and runs:
  ```
  cd ~/spark-vllm-docker && yes | ./run-recipe.sh -n <head_host>,<worker_host>,... <recipe>
  ```
- `run-recipe.sh` invokes `launch-cluster.sh` internally, which scps the launch script to workers, starts containers via SSH, and bootstraps the Ray cluster.
- The LaunchRecord is anchored to the head box; status, pause, inspect, and stop all act on the head's container.

This was selected over (B) explicit head-node selection via tag, and (C) sparkd-owned fan-out, because A introduces zero new orchestration code and matches the user's directive that spark-vllm-docker should orchestrate.

## Architecture changes

### 1. Target encoding + shared resolver

The `cluster:<name>` prefix already works in the advisor. Make it the universal target representation.

- **Schema rename**: `LaunchCreate.box_id: str` → `LaunchCreate.target: str`. Accepts either a raw box id or `cluster:<name>`. Same for the `GET /launches?box=<id>` filter, which becomes `?target=<id|cluster:name>`.
- **LaunchRecord**: keep `box_id` (= head box id) so existing UI that lists launches per box still works on the head's BoxDetailPage. Add `cluster_name: str | None` so the row can render a cluster pill.
- **New module** `sparkd/services/targets.py`:
  ```python
  @dataclass
  class ResolvedTarget:
      kind: Literal["box", "cluster"]
      head_box: BoxSpec        # box we SSH into
      members: list[BoxSpec]   # [head] for single-box; all members for cluster
      cluster_name: str | None

  async def resolve_target(target: str | None, boxes: BoxService) -> ResolvedTarget
  ```
  Used by LaunchService, AdvisorService, and OptimizeService. Replaces the duplicated `_resolve_caps` / `_resolve_cluster` helpers in `routes/advisor.py`.

### 2. Launch flow for clusters

`LaunchService.launch(body: LaunchCreate)`:

```
1. resolved = await resolve_target(body.target, boxes)
2. validate recipe against resolved.head_box.id        # existing path
3. recipe = library.load_recipe(name, box_id=resolved.head_box.id)
4. sync files to resolved.head_box only                # head-only sync; workers get files via launch-cluster.sh scp
5. if resolved.kind == "cluster":
       node_csv = ",".join(b.host for b in resolved.members)
       cmd = f"cd ~/spark-vllm-docker && yes | ./run-recipe.sh -n {node_csv} {recipe_slug}"
   else:
       cmd = f"cd ~/spark-vllm-docker && yes | ./run-recipe.sh {recipe_slug}"
6. SSH into resolved.head_box, capture PID + log path
7. return LaunchRecord(box_id=resolved.head_box.id, cluster_name=resolved.cluster_name, ...)
```

**Why head-only sync is correct**: upstream `launch-cluster.sh` scps the generated launch script to workers; the recipe YAML itself is only read by `run-recipe.py` on the head, which generates the launch script. Workers never see the recipe directly.

### 3. UI changes

- **New shared component** `frontend/src/components/TargetSelect.tsx`. Extracted from the optgrouped selector currently inlined in `AdvisorPage`. Single source of truth for "pick a target":
  ```tsx
  type TargetSelectProps = {
    value: string;                  // "" | "<box_id>" | "cluster:<name>"
    onChange: (next: string) => void;
    allowClusters?: boolean;        // default true
    allowDefault?: boolean;         // default false; shows "DGX Spark (default specs)"
    defaultLabel?: string;          // override the default-option label
  };
  ```
  Renders an optgrouped `<select>`: clusters under "clusters (multi-node)", boxes under "single box".

- **Use `<TargetSelect>` in:**
  - `AdvisorPage` — replaces the inline select; `allowDefault=true` to keep the "DGX Spark (default specs)" entry.
  - `OptimizePage` — replaces the single-box select; `allowDefault=true`.
  - `LaunchPage` — replaces the single-box select; `allowClusters=true`. The launch button passes `target` (not `box_id`) to `POST /launches`.
  - `RecipeAIAssist` — currently hardcodes `target_box_id: null`. Add a target picker so AI assist can target a cluster's caps.

- **`BoxesPage`**: remove the **"⟶ advise multi-node"** button from each cluster card per user request. The card stays informational (cluster name, node count, member list linking to BoxDetailPage).

- **`BoxDetailPage` cluster field — chip input**: replace the plain `<input>` with a chip-style picker (a.k.a. tag/token input). Behavior:
  - When empty, render an autocomplete `<input>`. As the user types, a dropdown shows existing cluster names from `useClusters()` filtered by the typed prefix; an "Enter to create `<typed>`" affordance appears for novel names.
  - Pressing **Tab** or **Enter** commits the value (selected suggestion or typed novel name) and writes `draft.tags.cluster = <value>`. The input is then replaced with a **chip** rendering the cluster name and a small **×** remove control.
  - Clicking **×** clears `draft.tags.cluster` and returns the field to the empty input state.
  - Only one chip can exist at a time (the data model stays `tags.cluster: string`). When a chip is present, the autocomplete input is hidden.
  - Clicking the chip body opens it back into editable input mode (chip → input with current value pre-filled), so the user can amend without removing-and-retyping.
  - Keyboard: **Backspace** in an empty input does nothing destructive (chip is already gone). **Esc** closes the suggestion dropdown without committing. Suggestion list is keyboard-navigable with ↑/↓.
  - Visual: chip uses the existing `Pill` token (`tone="info"`) with an inline `×` button, matching the cluster pills on `BoxesPage` for consistency.

  **Component**: new `frontend/src/components/ChipInput.tsx`. Single-value, autocomplete-backed, novel-value-allowed. Props:
  ```tsx
  type ChipInputProps = {
    value: string;                       // "" means no chip
    onChange: (next: string) => void;    // "" to clear
    suggestions: string[];               // list of existing values to autocomplete from
    placeholder?: string;
    chipTone?: "info" | "neutral";       // styling token
  };
  ```
  Self-contained — no third-party tag-input dependency. Built on the existing `Pill` component for chip rendering. Reusable for future tag-style inputs (e.g., per-box arbitrary tags) without lock-in.

- **Launch row rendering**: when `LaunchRecord.cluster_name` is present, render a small `Network` icon and a cluster pill alongside the box name on the launch list / status row, so multi-node launches are visually distinct.

### 4. Advisor route cleanup

`sparkd/routes/advisor.py` currently has local `CLUSTER_PREFIX`, `_resolve_caps`, `_resolve_cluster` helpers. Replace with `resolve_target` from the new module:

- `_resolve_caps` → `resolve_target(...).head_box.id` then `boxes.capabilities(head.id)` with the same default fallback.
- `_resolve_cluster` → if `resolved.kind == "cluster"`, build the topology dict from `resolved.members` (per-node caps fetched in a loop, totals aggregated). Same shape as today.

## Data flow (cluster launch, end-to-end)

```
Frontend LaunchPage
  → POST /launches { recipe, target: "cluster:alpha", mods }
Backend
  → resolve_target("cluster:alpha")
      = { kind: "cluster", head_box: gx10-0fb1, members: [gx10-0fb1, gx10-2c44, gx10-9af3], cluster_name: "alpha" }
  → validate recipe against gx10-0fb1
  → load_recipe(slug, box_id=gx10-0fb1.id)
  → sync to gx10-0fb1 only
  → ssh gx10-0fb1 'cd ~/spark-vllm-docker && yes | ./run-recipe.sh -n 10.0.0.11,10.0.0.12,10.0.0.13 <slug>'
Upstream on head
  → run-recipe.py builds launch script, calls launch-cluster.sh -n 10.0.0.11,10.0.0.12,10.0.0.13 ...
  → launch-cluster.sh scps script + Ray bootstrap to workers via SSH
  → starts containers on each node, head joins as Ray head, workers join as Ray workers
  → vLLM serve runs across all 3 nodes
Backend
  → captures head PID + log path on gx10-0fb1
  → returns LaunchRecord { box_id: "gx10-0fb1", cluster_name: "alpha", ... }
Frontend
  → status row shows host gx10-0fb1 with [alpha · 3 nodes] pill
```

## Files touched

**Backend (modify)**
- `sparkd/schemas/launch.py` — `box_id` → `target`; add `cluster_name: str | None` to `LaunchRecord`.
- `sparkd/services/launch.py` — call `resolve_target`, head-only sync, build `-n` flag for cluster targets, set `cluster_name` on record.
- `sparkd/routes/launches.py` — body uses `target`; `?box=` query → `?target=`.
- `sparkd/routes/advisor.py` — replace `_resolve_caps` / `_resolve_cluster` with `resolve_target`-based flow.
- `sparkd/services/advisor.py` — keep the public field name `target_box_id` (it already accepts `cluster:<name>`; no DB migration), just route resolution through `resolve_target`.

**Backend (new)**
- `sparkd/services/targets.py` — `ResolvedTarget`, `resolve_target`, `CLUSTER_PREFIX`.

**Frontend (modify)**
- `frontend/src/pages/LaunchPage.tsx` — use `<TargetSelect>`; rename state and request key from `box` → `target`.
- `frontend/src/pages/OptimizePage.tsx` — use `<TargetSelect>`.
- `frontend/src/pages/AdvisorPage.tsx` — replace inline select with `<TargetSelect>`.
- `frontend/src/pages/BoxesPage.tsx` — remove the "advise multi-node" button block.
- `frontend/src/pages/BoxDetailPage.tsx` — replace the plain cluster `<input>` with `<ChipInput>` driven by `useClusters()`.
- `frontend/src/components/RecipeAIAssist.tsx` — add `<TargetSelect>` for AI assist, pass `target_box_id` through.
- `frontend/src/hooks/useLaunches.ts` — request body uses `target`; query filter uses `?target=`.
- Launch list / status row component — render cluster pill when `cluster_name` is set.

**Frontend (new)**
- `frontend/src/components/TargetSelect.tsx` — shared selector.
- `frontend/src/components/ChipInput.tsx` — single-value autocomplete-backed chip input, used by the cluster field on `BoxDetailPage`.

**Tests**
- `tests/integration/test_launches_routes.py` — single-box (regression) + cluster launch test asserting `-n host1,host2,...` lands on the head's SSH command.
- `tests/integration/test_clusters_routes.py` — keep existing 5; no new cases here.
- `tests/unit/test_targets.py` — `resolve_target` for: `None`, raw box id, valid `cluster:<name>`, unknown cluster (should raise), unknown box (should raise).
- `tests/integration/test_advisor_routes.py` — update existing fakes to use `resolve_target` shape (no behavioral change to the assertions).

## Testing strategy

- **Unit**: `resolve_target` exercised directly. Single box id, cluster prefix, missing/unknown both. Pure logic, no SSH.
- **Integration**: existing FakeSSH harness extended to assert the exact head command for a cluster target — `./run-recipe.sh -n host1,host2,host3 <slug>`. Worker SSH paths are not exercised (upstream's job).
- **Regression**: the single-box launch path must keep emitting `./run-recipe.sh <slug>` with no `-n`. Existing launch tests pinned to that exact form.
- **Frontend build**: `npm run build` must pass. No new browser-side tests (component is presentational and tested through page-level usage).

## Risks & open questions

- **Host vs IP**: `box.host` may be a Tailscale name (e.g., `gx10-0fb1.local`) rather than a raw IP. Upstream `launch-cluster.sh` documentation refers to "node IPs" but in practice ssh-able hostnames work because it shells out to `ssh`/`scp`. We pass `box.host` as-is and treat any further translation as upstream's concern. If a user reports breakage, we add an optional `cluster_ip` override on the box later.
- **Head selection determinism**: First member is head. If a user wants explicit control, they can re-tag boxes or we add a `cluster_role=head` tag in a follow-up. Out of scope here.
- **Single launch row for a multi-node deployment**: monitoring is head-anchored. If a worker dies, sparkd has no view; the user sees the head container fail. Acceptable for now — upstream's responsibility.
- **Renaming `box_id` → `target`**: pre-release, we break cleanly. All call sites are in this repo.

## Out of scope (follow-ups)

- Per-node status panel for cluster launches.
- Explicit head-node selection via tag.
- Optional `cluster_ip` per-box override for IB-network IPs.
- Cluster-aware library views (e.g., recipes filtered by "compatible with this cluster size").
