from __future__ import annotations

import json
import logging
import shlex
import uuid
from datetime import datetime, timezone

import httpx
import yaml
from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import Box, Launch
from sparkd.errors import ConflictError, NotFoundError, ValidationError
from sparkd.schemas.launch import (
    ACTIVE_STATES,
    LaunchCreate,
    LaunchRecord,
    LaunchState,
)
from sparkd.services.box import BoxService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.services.targets import resolve_target
from sparkd.ssh.pool import SSHPool, SSHTarget

_log = logging.getLogger(__name__)


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

    async def _sync_files(
        self,
        name: str,
        box_id: str,
        mods: list[str],
        *,
        extra_env: dict[str, str] | None = None,
        strip_env_keys: list[str] | None = None,
    ) -> None:
        await self.recipes.sync(
            name, box_id, extra_env=extra_env, strip_env_keys=strip_env_keys
        )

    async def launch(self, body: LaunchCreate) -> LaunchRecord:
        resolved = await resolve_target(body.target, self.boxes)
        head_id = resolved.head_box.id
        recipe = self.library.load_recipe(body.recipe, box_id=head_id)
        # Build cluster topology dict (matching the advisor's shape) so
        # the validator can size tp×pp against the cluster's total GPUs
        # rather than just the head box's GPU count. Without this, every
        # cluster recipe with tp>head.gpu_count fails pre-flight even
        # when it fits the cluster budget perfectly.
        cluster_for_validate: dict | None = None
        if resolved.kind == "cluster":
            members_caps = []
            for m in resolved.members:
                try:
                    c = await self.boxes.capabilities(m.id)
                    members_caps.append(c.gpu_count)
                except Exception:  # noqa: BLE001
                    members_caps.append(0)
            cluster_for_validate = {
                "name": resolved.cluster_name,
                "nodes": [{"gpu_count": g} for g in members_caps],
                "total_gpus": sum(members_caps),
            }
        issues = await self.recipes.validate(
            recipe, head_id, cluster=cluster_for_validate
        )
        if issues:
            raise ValidationError(
                "recipe failed pre-flight validation",
                details={"issues": issues},
            )
        # Capture the upstream-format `container:` field too — RecipeSpec
        # doesn't carry it, but we need it later to find the running docker
        # container by image (ancestor) for pause/restart/inspect/stop.
        try:
            raw_yaml = self.library.load_recipe_text(
                body.recipe, box_id=head_id
            )
            raw_recipe = yaml.safe_load(raw_yaml) or {}
        except Exception:  # noqa: BLE001
            raw_recipe = {}
        container_image = (raw_recipe.get("container") or "vllm-node").strip()
        warnings: list[str] = []
        # At cluster sync time, strip env entries that reference $LOCAL_IP.
        # Why: upstream `run-recipe.py` writes the recipe's `env:` block as
        # `export KEY="VALUE"` lines into a bash script run inside each
        # container. Inside the container, $LOCAL_IP is NOT defined —
        # upstream's `launch-cluster.sh` sets per-node `-e VLLM_HOST_IP=…`,
        # `-e RAY_NODE_IP_ADDRESS=…`, etc., but never sets `LOCAL_IP`. So
        # `export VLLM_HOST_IP="$LOCAL_IP"` expands to `VLLM_HOST_IP=""` and
        # blows away the correctly-set value, making vLLM auto-detect the
        # eth IP and breaking Ray placement. (Past sparkd versions injected
        # this themselves; this strip undoes that damage even on existing
        # recipes the user already has on disk.)
        strip_env_keys: list[str] = []
        if resolved.kind == "cluster":
            recipe_env = raw_recipe.get("env") or {}
            if isinstance(recipe_env, dict):
                for k, v in recipe_env.items():
                    if isinstance(v, str) and "$LOCAL_IP" in v:
                        strip_env_keys.append(k)
            if strip_env_keys:
                warnings.append(
                    "Stripped env keys that reference $LOCAL_IP "
                    f"({', '.join(strip_env_keys)}) — that variable is "
                    "not defined inside the container, so the export "
                    "would blank out the value. Upstream's "
                    "launch-cluster.sh sets VLLM_HOST_IP/RAY_*/NCCL_* "
                    "per node via docker -e; recipes should not override."
                )
            # Warn if any member is missing cluster_ip — we'll fall back to
            # host (SSH name), which upstream launch-cluster.sh's literal
            # LOCAL_IP string-match will reject. Diagnose this LOUDLY at
            # the top of the launch log so the user doesn't spend an hour
            # chasing a Ray placement-group timeout that's actually a
            # one-field configuration gap.
            missing = [m for m in resolved.members if not m.cluster_ip]
            if missing:
                names = ", ".join(m.name for m in missing)
                warnings.append(
                    f"cluster_ip is not set on member(s): {names}. "
                    f"Falling back to SSH hostname in -n; upstream "
                    f"launch-cluster.sh's LOCAL_IP string-match will "
                    f"likely fail and the worker GPU will not register "
                    f"in the Ray placement group. Refresh capabilities "
                    f"on each member, or set cluster_ip manually on "
                    f"Box Detail."
                )
        await self._sync_files(
            body.recipe, head_id, body.mods, strip_env_keys=strip_env_keys
        )
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
                # Upstream launch-cluster.sh expects each node's LOCAL_IP
                # (the IB/eth-fabric address) and string-matches its own
                # against this list — hostnames don't match. Use cluster_ip
                # when set (auto-detected from .env or manually entered);
                # fall back to host so single-fabric setups keep working.
                node_csv = ",".join(
                    (b.cluster_ip or b.host) for b in resolved.members
                )
                run_cmd = f"./run-recipe.sh -n {node_csv} {body.recipe}"
            else:
                run_cmd = f"./run-recipe.sh {body.recipe}"
            # nohup + redirect so the recipe survives the SSH session closing,
            # and so log output goes to a known file we can tail later.
            # Recipe name + repo_path are validated/configured upstream so
            # they're safe to interpolate.
            #
            # Pipe `yes` into the script so the upstream `run-recipe.py`'s
            # interactive prompts (e.g. "Build now? [y/N]" on first run when
            # the vllm-node image hasn't been built yet) auto-answer "yes".
            # Without this, input() raises EOFError because we redirect
            # stdin from /dev/null and the launch fails before docker even
            # starts.
            # Sparkd-side log header — written before run-recipe.sh kicks
            # off so it always opens the launch log. Includes any warnings
            # so users see them in LiveLog rather than silently hitting a
            # cluster mis-config 90 seconds later.
            header_lines = [
                f"=== sparkd launch {launch_id} ===",
                f"recipe: {body.recipe}",
                f"target:  {body.target}",
            ]
            if resolved.kind == "cluster":
                node_summary = ",".join(
                    (m.cluster_ip or f"{m.host}(no cluster_ip)")
                    for m in resolved.members
                )
                header_lines.append(
                    f"cluster: {resolved.cluster_name} "
                    f"({len(resolved.members)} nodes: {node_summary})"
                )
            header_lines.extend(f"WARNING: {w}" for w in warnings)
            header = "\n".join(header_lines) + "\n\n"
            cmd = (
                f"mkdir -p ~/.sparkd-launches && "
                f"printf %s {shlex.quote(header)} > {log_path} && "
                f"( nohup bash -lc 'cd {box_row.repo_path} "
                f"&& yes | {run_cmd}' "
                f">> {log_path} 2>&1 < /dev/null & ) ; echo $!"
            )
        result = await self.pool.run(target, cmd)
        if result.exit_status not in (0, None):
            raise ConflictError(
                f"failed to start: {result.stderr.strip()}"
            )
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

    async def get(self, launch_id: str) -> LaunchRecord:
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            return _to_record(row)

    async def list(
        self,
        *,
        box_id: str | None = None,
        active_only: bool = False,
    ) -> list[LaunchRecord]:
        async with session_scope() as s:
            stmt = select(Launch)
            if box_id:
                stmt = stmt.where(Launch.box_id == box_id)
            if active_only:
                stmt = stmt.where(Launch.state.in_(list(ACTIVE_STATES)))
            rows = (await s.execute(stmt)).scalars().all()
            return [_to_record(r) for r in rows]

    # ---------- container action helpers ----------

    async def _target_and_row(self, launch_id: str) -> tuple[SSHTarget, Launch]:
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            box_row = await s.get(Box, row.box_id)
            target = self.boxes._target_for(box_row)
            return target, row

    async def _discover_container(
        self, target: SSHTarget, row: Launch
    ) -> str | None:
        """Find an addressable docker container started by ./run-recipe.sh
        for this launch. The upstream script doesn't accept extra `docker run`
        args so we can't tag the container; fall back to:
          1. filter `docker ps` by ancestor image (recipe's container: field).
             Accept running, paused, and restarting — exclude exited/dead.
          2. if multiple match, prefer one whose command contains the model
             id; otherwise take the most recent (docker ps lists newest first).
        """
        snap = row.recipe_snapshot_json or {}
        image = (snap.get("container") or "vllm-node").strip()
        model = (snap.get("model") or "").strip()
        if not image:
            return None
        out = await self.pool.run(
            target,
            f"docker ps --no-trunc --filter ancestor={shlex.quote(image)} "
            f"--filter status=running --filter status=paused "
            f"--filter status=restarting "
            f"--format '{{{{.ID}}}}|{{{{.Command}}}}'",
        )
        rows = [
            line.split("|", 1)
            for line in out.stdout.strip().splitlines()
            if line.strip()
        ]
        if not rows:
            return None
        if model:
            for r in rows:
                if len(r) == 2 and model in r[1]:
                    return r[0].strip()
        return rows[0][0].strip()

    async def _container_exists(self, target: SSHTarget, cid: str) -> bool:
        """Existence check (any state). After a `docker pause`, the container
        is in 'paused' state — addressable for unpause/restart/inspect/stop —
        but a strict `--filter status=running` check would treat it as stale
        and force re-discovery. Use `-a` so any state counts."""
        check = await self.pool.run(
            target,
            f"docker ps -a -q --filter id={shlex.quote(cid)}",
        )
        return bool(check.stdout.strip())

    async def _resolve_container(
        self, launch_id: str
    ) -> tuple[SSHTarget, Launch, str | None]:
        target, row = await self._target_and_row(launch_id)
        cid: str | None = row.container_id
        # Cached id might be stale: an `--rm` build/intermediate container
        # that exited and was removed, or a container we stopped+pruned.
        if cid and not await self._container_exists(target, cid):
            cid = None
        if not cid:
            cid = await self._discover_container(target, row)
            if cid:
                async with session_scope() as s:
                    db_row = await s.get(Launch, launch_id)
                    db_row.container_id = cid
        return target, row, cid

    async def _set_state(
        self,
        launch_id: str,
        state: LaunchState,
        *,
        container_id: str | None = None,
        stopped: bool = False,
        exit_info: dict | None = None,
    ) -> LaunchRecord:
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            row.state = state.value
            if container_id:
                row.container_id = container_id
            if stopped:
                row.stopped_at = datetime.now(timezone.utc)
            if exit_info is not None:
                row.exit_info_json = exit_info
            return _to_record(row)

    # ---------- public actions ----------

    async def stop(self, launch_id: str) -> LaunchRecord:
        target, _row, cid = await self._resolve_container(launch_id)
        if cid:
            await self.pool.run(target, f"docker stop {shlex.quote(cid)}")
        return await self._set_state(
            launch_id, LaunchState.stopped, container_id=cid, stopped=True
        )

    async def pause(self, launch_id: str) -> LaunchRecord:
        target, _row, cid = await self._resolve_container(launch_id)
        if not cid:
            raise NotFoundError("container", launch_id)
        result = await self.pool.run(target, f"docker pause {shlex.quote(cid)}")
        if result.exit_status not in (0, None):
            raise ConflictError(f"docker pause: {result.stderr.strip()}")
        return await self._set_state(launch_id, LaunchState.paused, container_id=cid)

    async def unpause(self, launch_id: str) -> LaunchRecord:
        target, _row, cid = await self._resolve_container(launch_id)
        if not cid:
            raise NotFoundError("container", launch_id)
        result = await self.pool.run(target, f"docker unpause {shlex.quote(cid)}")
        if result.exit_status not in (0, None):
            raise ConflictError(f"docker unpause: {result.stderr.strip()}")
        return await self._set_state(
            launch_id, LaunchState.healthy, container_id=cid
        )

    async def restart_container(self, launch_id: str) -> LaunchRecord:
        target, _row, cid = await self._resolve_container(launch_id)
        if not cid:
            raise NotFoundError("container", launch_id)
        result = await self.pool.run(target, f"docker restart {shlex.quote(cid)}")
        if result.exit_status not in (0, None):
            raise ConflictError(f"docker restart: {result.stderr.strip()}")
        return await self._set_state(
            launch_id, LaunchState.starting, container_id=cid
        )

    async def inspect(self, launch_id: str) -> dict:
        target, _row, cid = await self._resolve_container(launch_id)
        if not cid:
            return {"error": "no container found", "launch_id": launch_id}
        result = await self.pool.run(target, f"docker inspect {shlex.quote(cid)}")
        if result.exit_status not in (0, None):
            return {"error": result.stderr.strip(), "launch_id": launch_id}
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return {"error": f"could not parse docker inspect output: {exc}"}
        return {"container_id": cid, "inspect": data[0] if data else None}

    async def stats(self, launch_id: str) -> dict:
        target, _row, cid = await self._resolve_container(launch_id)
        if not cid:
            return {"error": "no container found"}
        result = await self.pool.run(
            target,
            f"docker stats --no-stream --format '{{{{json .}}}}' {shlex.quote(cid)}",
        )
        if result.exit_status not in (0, None):
            return {"error": result.stderr.strip()}
        line = result.stdout.strip()
        if not line:
            return {"error": "no stats output"}
        try:
            return {"container_id": cid, "stats": json.loads(line)}
        except json.JSONDecodeError:
            return {"container_id": cid, "stats": {"raw": line}}

    async def delete(self, launch_id: str) -> None:
        """Remove the launch row entirely (UI 'forget about this' action)."""
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                raise NotFoundError("launch", launch_id)
            await s.delete(row)

    # ---------- background reconciler ----------

    async def reconcile_active(self) -> None:
        """Probe each active launch and update its persisted state.

        Idempotent and safe to run on a timer. Driven by a background task
        in app.py so launch state stays in sync regardless of whether the
        web UI is connected — this is what makes a launch transition from
        `starting` to `healthy` once vLLM's OpenAI endpoint comes up.

        Per launch:
          - container missing  + state == healthy  → state = interrupted
          - container present  + vLLM 200s         → state = healthy
          - container present  + vLLM not 200      → state = starting
        Other transitions (paused/failed/stopped) are user-driven and not
        touched here.
        """
        async with session_scope() as s:
            rows = (
                await s.execute(
                    select(Launch).where(
                        Launch.state.in_(["starting", "healthy"])
                    )
                )
            ).scalars().all()
            items = [(r.id, r.state) for r in rows]
        for lid, state in items:
            try:
                await self._reconcile_one(lid, state)
            except Exception as exc:  # noqa: BLE001 — never break the loop
                _log.debug("reconcile failed for %s: %s", lid, exc)

    async def _reconcile_one(
        self, launch_id: str, current_state: str
    ) -> None:
        # _resolve_container is best-effort: it tries the cached id, falls
        # back to discovery via image. Returns cid=None when the container
        # is gone (e.g. --rm cleanup after vLLM exit, or the user stopped
        # it externally).
        try:
            target, _row, cid = await self._resolve_container(launch_id)
        except NotFoundError:
            return  # launch deleted between query and probe — fine

        if cid is None:
            # No container. If we previously saw it healthy, it crashed
            # or got removed → mark interrupted, capturing the tail of
            # the launch log so the user can see *why* without digging.
            # If we never saw it ("starting"), keep that state — upstream
            # may still be downloading the model image / weights, which
            # is slow on first launch.
            if current_state == "healthy":
                exit_info = await self._capture_exit_info(launch_id, target)
                await self._set_state(
                    launch_id,
                    LaunchState.interrupted,
                    stopped=True,
                    exit_info=exit_info,
                )
            return

        # Container is up. Probe vLLM /health on the head's host.
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                return
            box_row = await s.get(Box, row.box_id)
            if box_row is None:
                return
            host = box_row.host
        healthy = await self._probe_vllm(host)
        if healthy and current_state == "starting":
            await self._set_state(
                launch_id, LaunchState.healthy, container_id=cid
            )
        elif not healthy and current_state == "healthy":
            # Container is up but vLLM stopped responding. Could be a
            # temporary blip (compaction, OOM, model reload) or the
            # container's about to fall over. Drop back to "starting"
            # so the UI shows it as recovering — if the container goes
            # away entirely on the next tick we'll mark interrupted.
            await self._set_state(
                launch_id, LaunchState.starting, container_id=cid
            )

    async def _probe_vllm(self, host: str, port: int = 8000) -> bool:
        """Single HTTP probe against vLLM's /health endpoint. Short timeout
        so a slow box doesn't block the whole reconcile loop."""
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                r = await client.get(f"http://{host}:{port}/health")
                return r.status_code == 200
            except (httpx.HTTPError, ValueError):
                return False

    async def _capture_exit_info(
        self, launch_id: str, target: SSHTarget
    ) -> dict:
        """Capture a snapshot of the launch log when transitioning to a
        terminal state, so the UI can show *why* it died without the user
        having to ssh in and tail logs by hand. Best-effort — if the log
        is unreadable, return what we have.

        Schema:
          {
            "tail": [<last N lines, oldest first>],
            "reason": "<best-effort one-liner from tail>",
            "captured_at": "<ISO 8601>",
          }
        """
        async with session_scope() as s:
            row = await s.get(Launch, launch_id)
            if row is None:
                return {}
            log_path = row.log_path or f"~/.sparkd-launches/{launch_id}.log"

        # tail -n 30 — small enough to round-trip cheaply, large enough
        # to capture a Python traceback's "core" lines.
        tail_lines: list[str] = []
        try:
            result = await self.pool.run(
                target, f"tail -n 30 {shlex.quote(log_path)} 2>/dev/null"
            )
            if result.exit_status == 0:
                tail_lines = [
                    ln for ln in result.stdout.splitlines() if ln.strip()
                ]
        except Exception:  # noqa: BLE001
            pass

        return {
            "tail": tail_lines,
            "reason": _extract_reason(tail_lines),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }


def _extract_reason(tail: list[str]) -> str:
    """Best-effort one-liner explanation pulled from a launch log tail.

    Looks (in priority order) for: an OSError/RuntimeError/ValueError
    style line, a 'Tensor parallel' / 'CUDA out of memory' line, or any
    line starting with 'Error:'/'ERROR:'. Falls back to the last
    non-empty line. Truncated to 200 chars so the UI can render inline.
    """
    if not tail:
        return ""
    # Priority 1: explicit Python exception lines (last one wins — usually
    # the actual cause vs intermediate stack frames).
    exc_pattern = (
        "Error:", "Exception:", "OSError:", "RuntimeError:",
        "ValueError:", "KeyError:", "TypeError:", "ImportError:",
        "AssertionError:", "MemoryError:",
    )
    for line in reversed(tail):
        for marker in exc_pattern:
            if marker in line:
                return _truncate(line.strip())
    # Priority 2: vLLM's known fatal warnings.
    for line in reversed(tail):
        for marker in ("CUDA out of memory", "Tensor parallel", "FATAL"):
            if marker in line:
                return _truncate(line.strip())
    # Fallback: last non-empty line.
    return _truncate(tail[-1].strip())


def _truncate(s: str, n: int = 200) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"
