from __future__ import annotations

import shlex

import yaml

from sparkd.db.engine import session_scope
from sparkd.db.models import Box
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
        async with session_scope() as s:
            row = await s.get(Box, box_id)
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
