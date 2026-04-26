from __future__ import annotations

import json
import shlex
import uuid
from datetime import datetime, timezone

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
from sparkd.ssh.pool import SSHPool, SSHTarget


def _to_record(row: Launch) -> LaunchRecord:
    return LaunchRecord(
        id=row.id,
        box_id=row.box_id,
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
        # Capture the upstream-format `container:` field too — RecipeSpec
        # doesn't carry it, but we need it later to find the running docker
        # container by image (ancestor) for pause/restart/inspect/stop.
        try:
            raw_yaml = self.library.load_recipe_text(
                body.recipe, box_id=body.box_id
            )
            raw_recipe = yaml.safe_load(raw_yaml) or {}
        except Exception:  # noqa: BLE001
            raw_recipe = {}
        container_image = (raw_recipe.get("container") or "vllm-node").strip()
        await self._sync_files(body.recipe, body.box_id, body.mods)
        launch_id = uuid.uuid4().hex[:12]
        log_path = f"~/.sparkd-launches/{launch_id}.log"
        async with session_scope() as s:
            box_row = await s.get(Box, body.box_id)
            if box_row is None:
                raise NotFoundError("box", body.box_id)
            target = self.boxes._target_for(box_row)
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
            cmd = (
                f"mkdir -p ~/.sparkd-launches && "
                f"( nohup bash -lc 'cd {box_row.repo_path} "
                f"&& yes | ./run-recipe.sh {body.recipe}' "
                f"> {log_path} 2>&1 < /dev/null & ) ; echo $!"
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
                box_id=body.box_id,
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
        """Best-effort: find the running docker container started by
        ./run-recipe.sh for this launch. The upstream script doesn't accept
        extra `docker run` args so we can't tag the container; fall back to:
          1. filter `docker ps` by ancestor image (recipe's container: field)
             and status=running
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
            f"--filter status=running --format '{{{{.ID}}}}|{{{{.Command}}}}'",
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

    async def _container_running(self, target: SSHTarget, cid: str) -> bool:
        check = await self.pool.run(
            target,
            f"docker ps -q --filter id={shlex.quote(cid)} "
            f"--filter status=running",
        )
        return bool(check.stdout.strip())

    async def _resolve_container(
        self, launch_id: str
    ) -> tuple[SSHTarget, Launch, str | None]:
        target, row = await self._target_and_row(launch_id)
        cid: str | None = row.container_id
        # Cached id might be stale (build/intermediate container that's gone,
        # or a container we stopped earlier). Verify it's still running.
        if cid and not await self._container_running(target, cid):
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
