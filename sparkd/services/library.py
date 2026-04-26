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
        (d / f"{spec.name}.yaml").write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    def save_recipe_override(self, box_id: str, spec: RecipeSpec) -> None:
        _validate_name(spec.name)
        d = self._recipes_dir(box_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{spec.name}.yaml").write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    def load_recipe(self, name: str, *, box_id: str | None = None) -> RecipeSpec:
        _validate_name(name)
        if box_id is not None:
            override = self._recipes_dir(box_id) / f"{name}.yaml"
            if override.exists():
                return RecipeSpec(**yaml.safe_load(override.read_text()))
        canonical = self._recipes_dir(None) / f"{name}.yaml"
        if not canonical.exists():
            raise NotFoundError("recipe", name)
        return RecipeSpec(**yaml.safe_load(canonical.read_text()))

    def list_recipes(self, *, box_id: str | None = None) -> list[RecipeSpec]:
        d = self._recipes_dir(None)
        if not d.exists():
            return []
        out: dict[str, RecipeSpec] = {}
        for p in sorted(d.glob("*.yaml")):
            out[p.stem] = RecipeSpec(**yaml.safe_load(p.read_text()))
        if box_id:
            override_d = self._recipes_dir(box_id)
            if override_d.exists():
                for p in sorted(override_d.glob("*.yaml")):
                    out[p.stem] = RecipeSpec(**yaml.safe_load(p.read_text()))
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
        d = self._recipes_dir(None)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.yaml").write_text(yaml_text)
        # The slug used as filename wins for the parsed view; on-disk YAML untouched.
        return RecipeSpec(**{**parsed, "name": name})

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
