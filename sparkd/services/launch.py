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
            # recipe name + repo_path are validated/configured; safe to interpolate
            cmd = (
                f"bash -lc 'cd {box_row.repo_path} "
                f"&& ./run-recipe.sh {body.recipe}' & echo $!"
            )
        result = await self.pool.run(target, cmd)
        if result.exit_status not in (0, None):
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
