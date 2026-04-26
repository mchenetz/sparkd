from __future__ import annotations

import re
from pathlib import Path

import yaml

from sparkd import paths
from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.mod import ModSpec

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$")
# Allow leading `_` and `.` so files like `_triton_alloc_setup.pth` and
# `.gitignore` round-trip from upstream. Path traversal is blocked separately
# by the `..` and leading-`/` checks below.
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_.][a-zA-Z0-9_\-./]{0,127}$")


def _check_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValidationError(f"invalid mod name: {name!r}")


def _check_filename(name: str) -> None:
    if not _FILENAME_RE.match(name) or ".." in name or name.startswith("/"):
        raise ValidationError(f"invalid mod file path: {name!r}")


class ModService:
    def __init__(self) -> None:
        paths.ensure()

    def _dir(self, name: str) -> Path:
        return paths.library() / "mods" / name

    def save(self, spec: ModSpec) -> None:
        _check_name(spec.name)
        for f in spec.files:
            _check_filename(f)
        d = self._dir(spec.name)
        d.mkdir(parents=True, exist_ok=True)
        # Remove on-disk files that aren't in the new spec.files — keeps the
        # mod directory in sync with what the user just submitted (so e.g. a
        # file removed in the UI actually disappears from disk).
        keep = set(spec.files.keys())
        for p in list(d.rglob("*")):
            if not p.is_file() or p.name == "mod.yaml":
                continue
            rel = str(p.relative_to(d))
            if rel not in keep:
                p.unlink()
        # Prune empty subdirectories left behind by deletions.
        for p in sorted(d.rglob("*"), reverse=True):
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        meta = {
            "name": spec.name,
            "target_models": spec.target_models,
            "description": spec.description,
            "enabled": spec.enabled,
        }
        (d / "mod.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
        for fname, content in spec.files.items():
            target = d / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    def load(self, name: str) -> ModSpec:
        _check_name(name)
        d = self._dir(name)
        meta_path = d / "mod.yaml"
        if not meta_path.exists():
            raise NotFoundError("mod", name)
        meta = yaml.safe_load(meta_path.read_text()) or {}
        files: dict[str, str] = {}
        for p in d.rglob("*"):
            if not p.is_file() or p.name == "mod.yaml":
                continue
            rel = str(p.relative_to(d))
            files[rel] = p.read_text()
        return ModSpec(
            name=meta.get("name", name),
            target_models=list(meta.get("target_models") or []),
            description=meta.get("description", "") or "",
            files=files,
            enabled=bool(meta.get("enabled", True)),
        )

    def list(self) -> list[ModSpec]:
        root = paths.library() / "mods"
        if not root.exists():
            return []
        out: list[ModSpec] = []
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "mod.yaml").exists():
                out.append(self.load(d.name))
        return out

    def delete(self, name: str) -> None:
        _check_name(name)
        d = self._dir(name)
        if not d.exists():
            raise NotFoundError("mod", name)
        for p in sorted(d.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        d.rmdir()
