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
