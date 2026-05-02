from __future__ import annotations

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

    async def sync(
        self,
        name: str,
        box_id: str,
        *,
        extra_env: dict[str, str] | None = None,
        strip_env_keys: list[str] | None = None,
    ) -> None:
        """Push the recipe YAML to the head box.

        Normally we forward the raw on-disk YAML byte-identical so
        upstream-format recipes (with `defaults`, `command`, `container`,
        etc.) round-trip exactly and remain runnable by the box's
        ./run-recipe.sh.

        Two transformations are supported, both applied to a parsed copy
        of the YAML so the on-disk file is never mutated:

        - `extra_env`: defaults-only merge into `env:`. Keys already
          present in the recipe are left alone.
        - `strip_env_keys`: remove these keys from `env:` entirely. Used
          by the cluster launch path to drop entries that reference
          `$LOCAL_IP` (a variable upstream does not set inside the
          container) before they reach the box and break vLLM's host-IP
          discovery.
        """
        yaml_text = self.library.load_recipe_text(name, box_id=box_id)
        data = yaml.safe_load(yaml_text) or {}
        mutated = False

        # Defensive: mirror top-level `model:` into `defaults.model` if the
        # command references `{model}` and defaults doesn't already have it.
        # Upstream's run-recipe.py uses `defaults` as the str.format namespace
        # and treats the top-level `model:` field as metadata only — so a
        # command with `{model}` and no `defaults.model` crashes with
        # "Missing parameter in recipe command: 'model'". This unbreaks
        # recipes saved by older sparkd versions whose renderer omitted the
        # mirror, without requiring manual edits.
        command = data.get("command") or ""
        top_model = data.get("model")
        if (
            isinstance(command, str)
            and "{model}" in command
            and isinstance(top_model, str)
            and top_model
        ):
            defaults = data.get("defaults") or {}
            if isinstance(defaults, dict) and "model" not in defaults:
                defaults["model"] = top_model
                data["defaults"] = defaults
                mutated = True

        # Strip + merge env entries if requested.
        if extra_env or strip_env_keys:
            env = data.setdefault("env", {}) or {}
            data["env"] = env
            if strip_env_keys:
                before = len(env)
                for k in strip_env_keys:
                    env.pop(k, None)
                if len(env) != before:
                    mutated = True
            if extra_env:
                for k, v in extra_env.items():
                    if k not in env:
                        env[k] = v
                        mutated = True

        if mutated:
            yaml_text = yaml.safe_dump(
                data, sort_keys=False, default_flow_style=False
            )
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
