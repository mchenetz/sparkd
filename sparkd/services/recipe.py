from __future__ import annotations

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
        # Push the raw on-disk YAML so upstream-format recipes (with `defaults`,
        # `command`, `container`, etc.) round-trip byte-identical and remain
        # runnable by the box's ./run-recipe.sh.
        yaml_text = self.library.load_recipe_text(name, box_id=box_id)
        if not yaml_text.endswith("\n"):
            yaml_text += "\n"
        box = await self.boxes.get(box_id)
        async with session_scope() as s:
            row = await s.get(Box, box_id)
            target = self.boxes._target_for(row)
        # Don't shlex.quote repo_path or name here:
        # - quoting `~/spark-vllm-docker` produces `'~/...'` which suppresses
        #   tilde expansion, dropping files into a literal `~` directory.
        # - name is already validated by LibraryService._NAME_RE; repo_path is
        #   user-set config (the user is the only one who can hurt themselves).
        await self.pool.run(target, f"mkdir -p {box.repo_path}/recipes")
        cmd = (
            f"cat > {box.repo_path}/recipes/{name}.yaml "
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
