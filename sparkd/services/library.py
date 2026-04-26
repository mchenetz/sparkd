from __future__ import annotations

import re
from pathlib import Path

import yaml

from sparkd import paths
from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.recipe import RecipeSpec

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")


def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValidationError(f"invalid name: {name!r}")


class LibraryService:
    def __init__(self) -> None:
        paths.ensure()

    def _recipes_dir(self, box_id: str | None) -> Path:
        if box_id is None:
            return paths.library() / "recipes"
        return paths.boxes_dir() / box_id / "overrides" / "recipes"

    def save_recipe(self, spec: RecipeSpec) -> None:
        _validate_name(spec.name)
        d = self._recipes_dir(None)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{spec.name}.yaml").write_text(_render_upstream_yaml(spec))

    def save_recipe_override(self, box_id: str, spec: RecipeSpec) -> None:
        _validate_name(spec.name)
        d = self._recipes_dir(box_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{spec.name}.yaml").write_text(_render_upstream_yaml(spec))

    def load_recipe(self, name: str, *, box_id: str | None = None) -> RecipeSpec:
        _validate_name(name)
        # The filename stem is the canonical identifier we use everywhere
        # (URLs, sync paths, save_recipe_raw). Override whatever `name:` the
        # YAML's body says so the parsed view's identity matches the slug.
        # (Pretty internal names from upstream stay verbatim on disk.)
        if box_id is not None:
            override = self._recipes_dir(box_id) / f"{name}.yaml"
            if override.exists():
                data = yaml.safe_load(override.read_text()) or {}
                return RecipeSpec(**{**data, "name": name})
        canonical = self._recipes_dir(None) / f"{name}.yaml"
        if not canonical.exists():
            raise NotFoundError("recipe", name)
        data = yaml.safe_load(canonical.read_text()) or {}
        return RecipeSpec(**{**data, "name": name})

    def list_recipes(self, *, box_id: str | None = None) -> list[RecipeSpec]:
        d = self._recipes_dir(None)
        if not d.exists():
            return []
        out: dict[str, RecipeSpec] = {}
        for p in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(p.read_text()) or {}
            out[p.stem] = RecipeSpec(**{**data, "name": p.stem})
        if box_id:
            override_d = self._recipes_dir(box_id)
            if override_d.exists():
                for p in sorted(override_d.glob("*.yaml")):
                    data = yaml.safe_load(p.read_text()) or {}
                    out[p.stem] = RecipeSpec(**{**data, "name": p.stem})
        return list(out.values())

    def delete_recipe(self, name: str) -> None:
        _validate_name(name)
        f = self._recipes_dir(None) / f"{name}.yaml"
        if not f.exists():
            raise NotFoundError("recipe", name)
        f.unlink()

    def has_recipe(self, name: str) -> bool:
        _validate_name(name)
        return (self._recipes_dir(None) / f"{name}.yaml").exists()

    def update_recipe(self, spec: RecipeSpec) -> None:
        """Merge spec fields into the existing on-disk YAML.

        Unlike save_recipe (which writes the spec verbatim), this preserves any
        unmodeled fields already in the YAML — e.g. upstream `defaults`,
        `command`, `container`, `recipe_version`. If no file exists yet, falls
        back to save_recipe.
        """
        _validate_name(spec.name)
        f = self._recipes_dir(None) / f"{spec.name}.yaml"
        if not f.exists():
            self.save_recipe(spec)
            return
        existing = yaml.safe_load(f.read_text()) or {}
        if not isinstance(existing, dict):
            raise ValidationError(
                f"existing recipe {spec.name!r} is not a YAML mapping; "
                "edit via the YAML view"
            )
        updates = spec.model_dump()
        # The slug (filename) is the identifier; we don't write it back into
        # the YAML body, since the on-disk `name:` may be a pretty display
        # name we want to preserve verbatim for upstream-format recipes.
        updates.pop("name", None)
        existing.update(updates)
        f.write_text(yaml.safe_dump(existing, sort_keys=False))

    def save_recipe_raw(self, name: str, yaml_text: str) -> RecipeSpec:
        """Persist YAML verbatim (for upstream-format recipes) and return a parsed view.

        Use this when the YAML may contain fields outside RecipeSpec (e.g. upstream
        spark-vllm-docker recipes have `defaults`, `command`, `container`,
        `recipe_version`). The on-disk file preserves all keys; load_recipe_text()
        round-trips byte-for-byte for sync-to-box.
        """
        _validate_name(name)
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict):
            raise ValidationError("recipe yaml must be a mapping at the top level")
        if not parsed.get("model"):
            raise ValidationError(f"recipe {name!r} has no model field")
        # Validate the parsed view BEFORE touching disk, so a failed validation
        # never leaves an orphan file behind. The slug used as filename wins;
        # on-disk YAML is preserved verbatim once we get past validation.
        try:
            spec = RecipeSpec(**{**parsed, "name": name})
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(
                f"recipe {name!r} failed schema validation: {exc}"
            ) from exc
        d = self._recipes_dir(None)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.yaml").write_text(yaml_text)
        return spec

    def load_recipe_text(self, name: str, *, box_id: str | None = None) -> str:
        """Return the raw YAML bytes for a recipe — preferring per-box override."""
        _validate_name(name)
        if box_id is not None:
            override = self._recipes_dir(box_id) / f"{name}.yaml"
            if override.exists():
                return override.read_text()
        canonical = self._recipes_dir(None) / f"{name}.yaml"
        if not canonical.exists():
            raise NotFoundError("recipe", name)
        return canonical.read_text()


def _yaml_inline(value: object) -> str:
    """Compact yaml.safe_dump output suitable for inline values.

    Strips trailing newline and the `...` document-end marker that yaml emits
    for plain scalars in flow style (e.g. dump('bar') → 'bar\\n...\\n').
    """
    out = yaml.safe_dump(
        value, default_flow_style=True, sort_keys=False, width=10_000
    )
    out = out.rstrip("\n")
    if out.endswith("\n..."):
        out = out[: -len("\n...")]
    return out


def _block_dict(name: str, d: dict) -> str:
    """`name: {}` if empty, else `name:\\n  k: v\\n  ...`."""
    if not d:
        return f"{name}: {{}}"
    body = "\n".join(f"  {k}: {_yaml_inline(v)}" for k, v in d.items())
    return f"{name}:\n{body}"


def _block_list(name: str, items: list) -> str:
    if not items:
        return f"{name}: []"
    body = "\n".join(f"  - {_yaml_inline(item)}" for item in items)
    return f"{name}:\n{body}"


def _render_upstream_yaml(spec: RecipeSpec) -> str:
    """Render a RecipeSpec in the upstream eugr/spark-vllm-docker layout
    (recipe_version / name / description / model / container / mods / args /
    defaults / env / command). Comments + field order match the in-repo
    examples so sparkd-saved recipes look like the synced ones.

    The on-disk YAML is the source of truth — RecipeSpec fields not relevant
    to upstream (args is sparkd-only) are still emitted so the round-trip
    preserves them.
    """
    description = spec.description or f"vLLM serving {spec.model}"
    return (
        f'recipe_version: "1"\n'
        f"name: {spec.name}\n"
        f"description: {description}\n"
        f"\n"
        f"# HuggingFace model id served by vLLM.\n"
        f"model: {spec.model}\n"
        f"\n"
        f"# Container image to use (built by ./build-and-copy.sh).\n"
        f"container: vllm-node\n"
        f"\n"
        f"# Optional list of mods applied alongside this recipe.\n"
        f"{_block_list('mods', list(spec.mods))}\n"
        f"\n"
        f"# sparkd-tracked CLI flags (informational; the upstream runner uses\n"
        f"# the templated `command` below). Edit them via the Form view.\n"
        f"{_block_dict('args', dict(spec.args))}\n"
        f"\n"
        f"# Default settings (referenced as {{var}} in the command template,\n"
        f"# can be overridden at launch via CLI flags).\n"
        f"defaults:\n"
        f"  port: 8000\n"
        f"  host: 0.0.0.0\n"
        f"  tensor_parallel: 1\n"
        f"  gpu_memory_utilization: 0.9\n"
        f"  max_model_len: 32768\n"
        f"\n"
        f"# Environment variables passed into the container.\n"
        f"{_block_dict('env', dict(spec.env))}\n"
        f"\n"
        f"# vLLM serve command template — {{var}} is substituted from\n"
        f"# `defaults` (or CLI overrides) at launch time.\n"
        f"command: |\n"
        f"  vllm serve {{model}} \\\n"
        f"    --host {{host}} \\\n"
        f"    --port {{port}} \\\n"
        f"    --gpu-memory-utilization {{gpu_memory_utilization}} \\\n"
        f"    --max-model-len {{max_model_len}} \\\n"
        f"    -tp {{tensor_parallel}}\n"
    )
