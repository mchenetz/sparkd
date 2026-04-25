# sparkd — DGX Spark vLLM Dashboard Design

**Date:** 2026-04-25
**Status:** Draft, awaiting user review
**Upstream project:** [eugr/spark-vllm-docker](https://github.com/eugr/spark-vllm-docker)

## 1. Goals & non-goals

`sparkd` is a localhost web dashboard for managing vLLM workloads on NVIDIA DGX Spark hardware via the `spark-vllm-docker` project. The user runs it on their own laptop; it connects to one or more DGX Spark boxes over SSH.

### v1 goals (single-box end-to-end)

- Connect to one or more DGX Spark boxes over SSH (manual entry plus optional subnet scan).
- Manage a local recipe library with per-box overrides.
- AI-assisted recipe creation from a Hugging Face model id, and AI-assisted optimization of existing recipes.
- Browse and apply mods, plus AI-assisted authoring of new mods from an error log or model.
- Launch recipes on a chosen box, stream logs, see status (Docker container state and vLLM endpoint health reconciled).
- Stop, restart, and inspect running models.

### Explicit non-goals for v1

- Multi-Spark orchestration. Deferred to v2; architected for via a `Cluster` service stub.
- Centralized multi-user deployment.
- Authentication beyond the user's own SSH agent and keys.
- Auto-deploying or installing the `spark-vllm-docker` repo on a box. Assumed already cloned and runnable.
- Hardware monitoring beyond what `nvidia-smi` over SSH provides.
- Remote-team collaboration or shared recipe library. Optional `git init` of the local library is the manual escape hatch.

## 2. Architecture overview

### Process layout

```
Browser  →  http://localhost:8765
   React SPA (Vite + TypeScript)
        │ REST + WebSocket (typed via OpenAPI → TS)
        ▼
FastAPI app (uvicorn, single process)
   HTTP layer / WS layer / Static asset serving
        │
   Domain services (one module each):
     Box, Recipe, Mod, Launch, Advisor,
     Library, HFCatalog, Status, Cluster
        │
   Infrastructure:
     SSH pool (asyncssh, multiplexed per box)
     SQLite (state)
     AI adapter port → AnthropicAdapter (v1), pluggable
        │
        ▼
   SSH → DGX Spark box(es)
         └─ docker, vllm, git, nvidia-smi
```

### On-laptop storage

```
~/.sparkd/
  config.toml             # global settings, AI provider choice
  state.db                # SQLite: boxes, launches, advisor sessions, audit log
  library/                # canonical recipes + mods (optionally a git repo)
    recipes/<name>.yaml
    mods/<name>/...
  boxes/<box-id>/
    overrides/recipes/...
    overrides/mods/...
  logs/                   # rotating local logs of launches & SSH
```

Secrets live in the OS keyring (macOS Keychain via the `keyring` library), never in `config.toml` or `state.db`.

### Cross-cutting choices

- **Async throughout.** `asyncio` plus `asyncssh`; long operations never block the request loop.
- **Persistent SSH multiplex per box.** One `asyncssh.SSHClientConnection` is reused for `docker ps`, log streaming, and file ops. Reconnect with backoff on failure.
- **Background jobs** via `asyncio.create_task` plus a `JobRegistry`. State is in-memory; a snapshot row is written to SQLite on every transition so that on restart, jobs left in `running` state are marked `interrupted` (they did not survive the process exit). No external worker.
- **Type contract.** Pydantic models → FastAPI → OpenAPI → `openapi-typescript` → React. One source of truth for schemas.
- **WebSocket channels:** `/ws/launches/{id}` for live launch logs, `/ws/boxes/{id}/status` for live status, `/ws/advisor/{session}` for streamed AI tokens.

## 3. Domain services

Each service is its own module under `sparkd/services/`. Pure logic; the HTTP and WS layer is a thin shell over the services. No service reaches into another service's storage; it only calls public methods.

### `BoxService`

Registry and connection lifecycle.

- CRUD on `Box` records: host, port, user, ssh-key path or agent flag, friendly name, tags.
- `discover(cidr)`: async subnet scan. TCP probe → SSH banner → `nvidia-smi -L | grep GB10` to confirm DGX Spark.
- Owns the SSH connection pool. Exposes `box.run(cmd)`, `box.sftp()`, and `box.stream(cmd)` to other services.
- Health: 30s heartbeat. States are `online`, `offline`, `degraded`.

### `LibraryService`

Local canonical recipes and mods on the laptop.

- Filesystem-backed at `~/.sparkd/library/`. Optional `git init` for history.
- A recipe is a YAML file. A mod is a directory containing `mod.yaml`, `patch.diff`, and an optional `hook.sh`.
- Validates against Pydantic models `RecipeSpec` and `ModSpec`.
- Computes the per-box effective view by merging overrides over canonical files.

### `RecipeService`

Recipe domain operations.

- CRUD via `LibraryService`. Sync-push to a target box via SFTP into the repo's `recipes/` directory.
- `validate(recipe, box)`: sanity-check against box capabilities (VRAM, GPU count, GB10 revision).
- Diff between two recipes. Clone-with-modifications.

### `ModService`

Same shape as `RecipeService` for mods.

- Browse, apply (toggle on/off in a launch context), validate that a patch applies cleanly.
- Author from template: scaffolds the directory.

### `AdvisorService`

The AI piece. Pluggable.

- `AdvisorPort` interface. `AnthropicAdapter` ships in v1.
- Three operations:
  - `generate_recipe(hf_model_id, target_box) → RecipeDraft + rationale`
  - `optimize_recipe(recipe, target_box, goals) → RecipeDiff + rationale`
  - `propose_mod(error_log_or_model, context) → ModDraft + rationale`
- Sessions stored in SQLite (`advisor_sessions` table). Preserves context across messages and enables prompt caching for cheap follow-ups.
- Streams tokens to the client over `/ws/advisor/{session}`.

### `HFCatalogService`

Hugging Face metadata fetcher.

- Reads model card, `config.json`, parameter count, supported dtypes from HF Hub.
- Caches per-model in SQLite with a 24h TTL.
- Feeds `AdvisorService` with grounded facts so it does not hallucinate model specs.

### `LaunchService`

Running models lifecycle.

- `launch(recipe, box, mods=[], overrides={})`: pushes recipe and enabled mods to the box if changed (content-hash compared), runs `./run-recipe.sh` over SSH, captures container id.
- `stop(launch_id)`, `restart(launch_id)`, `logs(launch_id)` (live tail and historical).
- Persists `Launch` records: status, container id, recipe snapshot, started/stopped timestamps, exit info.

### `StatusService`

Reconciliation engine for what is actually running.

- Per-box poll loop (5s when UI focused on the box, 30s background).
- `docker ps --format` plus `curl :8000/v1/models` plus `:8000/health`.
- Reconciles against `LaunchService` records. Flags drift: containers without a launch row, or launch rows without a container.
- Publishes deltas on `/ws/boxes/{id}/status`.

### `ClusterService`

Stub in v1, real in v2.

- Interface defined now: `launch_across`, `topology`, `health`. The single-box implementation just delegates to one `LaunchService` call.
- Lets v2 add multi-Spark orchestration without API breakage.

### Dependency direction

```
HTTP/WS  →  Recipe / Mod / Launch / Advisor / Status
            │                │
            ├──→ Library (recipes + mods on disk)
            ├──→ Box (SSH + capabilities)
            ├──→ AI adapter (Advisor only)
            └──→ SQLite (state)

Advisor  →  HFCatalog (facts grounding)
```

## 4. Key data flows

### Flow A — Generate a recipe for a Hugging Face model

1. UI: user picks the box, pastes or searches a HF model id, clicks **Generate**.
2. `POST /advisor/recipe` → `AdvisorService.generate_recipe(hf_id, box_id)`.
3. Advisor fetches in parallel:
   - `HFCatalogService.fetch(hf_id)`: parameters, architecture, dtypes, context length. Cached 24h.
   - `BoxService.capabilities(box_id)`: cached `nvidia-smi` output. GPU count, VRAM, GB10 revision, IB iface.
4. Advisor builds a prompt with both fact sets and opens an Anthropic streaming call via `AnthropicAdapter`. The system prompt, capabilities, and model facts are marked as cacheable so follow-up "tweak this" turns are cheap.
5. Tokens stream back over `/ws/advisor/{session_id}` as they arrive. The structured `RecipeDraft` is emitted as the final JSON message.
6. UI shows draft and rationale side-by-side. User can edit, accept, or chat further; each turn reuses the cached context.
7. On accept: `RecipeService.create(draft)` writes to `~/.sparkd/library/recipes/<name>.yaml`. If the user toggles "save as box override", writes to `boxes/<id>/overrides/recipes/`.

**Failure paths.** HF fetch fails: advisor gets a placeholder plus a warning, still attempts based on model-name conventions. Box offline: capabilities fall back to last cached snapshot with a staleness warning. Anthropic 429/5xx: exponential retry, then surface the error with the partial stream preserved.

### Flow B — Launch a recipe on a box

1. UI: select recipe, target box, optional mods. Click **Launch**.
2. `POST /launches` → `LaunchService.launch(recipe, box, mods)`.
3. Pre-flight, all parallel:
   - `RecipeService.validate(recipe, box)`: VRAM and GPU sanity vs. tp setting.
   - `ModService.validate(mods, box)`: patches apply cleanly.
   - `StatusService.box_busy(box)`: warn if a vLLM container already binds the port.
4. Sync step: SFTP recipe and each enabled mod into the repo on the box. Only files that differ are pushed (content-hash compared).
5. SSH: `cd ~/spark-vllm-docker && ./run-recipe.sh <name> > /var/log/sparkd/<launch_id>.log 2>&1 &`. Capture PID and container id once Docker emits it.
6. `Launch` row written to SQLite. Status `starting`, recipe snapshot, mod set, command, container id.
7. WebSocket `/ws/launches/{id}` pipes SSH stdout and stderr to the UI live. The same stream is tee'd to `~/.sparkd/logs/`.
8. `StatusService` poll loop picks up the new container next tick. Reconciles. Transitions `starting → healthy` (vLLM `/health` 200) or `starting → failed` (container exited or health timeout).

**Failure paths.** SFTP fails: abort, no launch row written. Container exits during start: status moves to `failed` and captured stderr is attached to the launch record. SSH disconnects mid-stream: reconnect, re-attach to logs via `docker logs --since`.

### Flow C — Status view across boxes

1. UI subscribes to `/ws/boxes/status` (one stream per visible box).
2. `StatusService` runs per-box polls:
   - `docker ps --format '{{json .}}' --filter label=sparkd` over the multiplexed SSH connection.
   - `GET http://<box>:8000/v1/models` and `/health` with a 1s timeout.
3. Reconciliation against `Launch` records produces a `BoxStatus` snapshot:
   - `running_models[]`: each entry has `{recipe?, container_id, vllm_model_id, healthy, started_at, source: dashboard|external}`.
   - `drift[]`: containers without a matching launch row, or launch rows with no container.
4. Diff against the last snapshot. Emit only the delta on the WS.
5. UI maintains a live table. `external` containers get a "claim" button that creates a launch record for them.

**Failure paths.** Box unreachable: `BoxStatus.connectivity = offline`. Last-known state is kept dimmed. vLLM `:8000` open but `/health` 5xx: model marked `degraded` and surfaces in the UI.

## 5. API surface

REST for CRUD and commands. WebSocket for streams. Requests and responses are typed Pydantic models; schemas are regenerated to TypeScript via `openapi-typescript` on build.

```
# Boxes
GET    /boxes                          → Box[]
POST   /boxes                          # manual add
PATCH  /boxes/{id}
DELETE /boxes/{id}
POST   /boxes/discover                 # body: {cidr, ssh_user, ssh_port?}, returns job_id
GET    /jobs/{id}                      # discovery + other long jobs
GET    /boxes/{id}/capabilities        # nvidia-smi snapshot, cached
POST   /boxes/{id}/test                # SSH + repo presence check

# Library (recipes + mods)
GET    /recipes                        ?box={id}   # effective merged view if box given
POST   /recipes
GET    /recipes/{name}
PUT    /recipes/{name}
DELETE /recipes/{name}
POST   /recipes/{name}/clone
GET    /recipes/{name}/diff?against={name|box}
POST   /recipes/{name}/validate?box={id}
POST   /recipes/{name}/sync?box={id}   # push override or canonical to box

GET    /mods
POST   /mods
GET    /mods/{name}
PUT    /mods/{name}
DELETE /mods/{name}

# Advisor (AI)
POST   /advisor/sessions               → {session_id}
POST   /advisor/sessions/{id}/recipe   # generate from HF id
POST   /advisor/sessions/{id}/optimize # optimize existing recipe
POST   /advisor/sessions/{id}/mod      # propose mod
POST   /advisor/sessions/{id}/message  # follow-up turn
GET    /advisor/sessions/{id}          # transcript

# Hugging Face
GET    /hf/models?q=...                # search proxy
GET    /hf/models/{id}                 # cached metadata

# Launches
POST   /launches                       # body: {recipe, box, mods?, overrides?}
GET    /launches?box={id}&status={...}
GET    /launches/{id}
POST   /launches/{id}/stop
POST   /launches/{id}/restart
GET    /launches/{id}/logs?since=...   # historical log slice

# Status
GET    /boxes/{id}/status              # one-shot snapshot

# Cluster (v1 stub, v2 real)
POST   /clusters/launches              # 501 in v1, contract reserved

# WebSocket
/ws/jobs/{id}                          # discovery progress, sync progress
/ws/boxes/{id}/status                  # live status deltas
/ws/launches/{id}                      # live log + state transitions
/ws/advisor/{session}                  # streamed AI tokens + structured drafts
```

**Auth.** None. The server binds to `127.0.0.1` only. A random per-session token is set in a cookie on first GET to defeat DNS-rebinding attacks. No remote access in v1.

**Errors.** RFC 7807 `application/problem+json`. Each domain raises a typed `DomainError` that the HTTP layer maps to a status and a `problem` body.

## 6. Testing strategy

### Unit tests (fast, no I/O)

Each service has a sibling `test_*.py`.

- `LibraryService`: fixtures of recipe and mod files in a tmp dir. Round-trip parse, write, and merge.
- `RecipeService.validate`: table-driven (recipe × box capabilities → expected verdict).
- `AdvisorService`: `AdvisorPort` faked. Assert prompt construction, output parsing, and error retry.
- `StatusService`: feed canned `docker ps` JSON and canned vLLM responses. Assert reconciliation deltas.
- `LaunchService`: `BoxService` faked to record SSH commands. Assert command shape and state transitions.

### Integration tests

Real SQLite, real filesystem, fake SSH transport.

- Use `asyncssh`'s in-process `SSHServer` to script canned responses for `docker ps`, `nvidia-smi`, `./run-recipe.sh`.
- HF Hub stubbed with an httpx mock serving fixtures.
- Anthropic stubbed with a recorded-tape replay (real responses captured once, replayed deterministically).

### End-to-end smoke

Opt-in. Requires a real DGX Spark box.

- `pytest -m e2e`. Needs `SPARKD_E2E_BOX` env var. Runs discovery → launch → stop. Skipped in CI by default.

### Frontend tests

- Component tests with Vitest and Testing Library.
- One Playwright test per major flow (add box, generate recipe, launch, view status) against a mocked backend.
- No real-box browser tests.

### Coverage target

80% on services. No target on the HTTP/WS layer; it is thin.

## 7. Observability

- **Structured logging.** `structlog` JSON output to `~/.sparkd/logs/sparkd.jsonl`. Pretty console output. Every log includes `box_id`, `launch_id`, and `session_id` where relevant.
- **Audit table** in SQLite: `audit_log(ts, actor, action, target, payload_json)` for every mutating op (add box, push recipe, launch, AI prompt). User-visible at `/audit` in the UI.
- **Health endpoint.** `GET /healthz` reports SSH pool sizes, AI adapter status, DB OK, and disk usage of `~/.sparkd/`.
- **No metrics export** in v1 (single-laptop tool). Hooks left for Prometheus later.
- **AI cost meter.** `AdvisorService` records input and output tokens per call. UI shows the running session total and lifetime totals.

## 8. Packaging and ops

- **Distribution.** `uv tool install sparkd` (or `pipx`). Single `sparkd` entrypoint that boots uvicorn and serves built React assets from the same process.
- **First-run wizard.** On first launch, opens the browser at `localhost:8765/setup`. Collects the Anthropic key (stored in the OS keyring), confirms the `~/.sparkd/` location, and offers an optional `git init` of the library.
- **Updates.** Standard `uv tool upgrade sparkd`. SQLite migrations via `alembic`, run on startup.
- **Config file.** `~/.sparkd/config.toml` for non-secret prefs (theme, default box, log retention).
- **Backup.** `sparkd export` and `sparkd import` zip the library and config (not `state.db`, not secrets) for moving between machines.

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| SSH connection storms during status polling | Persistent multiplex per box; one connection serves all polls |
| AI hallucinates impossible recipes | Validate against box capabilities before accept; advisor prompt explicitly fed real `nvidia-smi` data |
| User has many boxes; polling gets heavy | Adaptive poll interval — 5s when UI is open on that box, 30s background |
| Anthropic API key leak | OS keyring only; `config.toml` never holds it; `sparkd export` excludes secrets |
| Recipe/mod drift between laptop and box | Content-hash compare on every sync; UI shows drift badge |
| `run-recipe.sh` semantics change upstream | Pin tested commit of `spark-vllm-docker`; capability-detect via `--help` parsing |

## 10. Open questions for v2

- Multi-Spark orchestration semantics: tensor-parallel across boxes vs. independent replicas behind a router.
- Shared library across teammates: git remote sync, or a small server.
- Optional in-box agent for lower-latency status streams.
- Local-LLM advisor adapter for offline use.
