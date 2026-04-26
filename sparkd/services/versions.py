"""Append-only history of recipe YAML snapshots.

Every time a recipe's YAML changes (form save, raw save, upstream sync, AI
apply, revert), a row is added to recipe_versions. Revert is itself a save —
restoring an older snapshot becomes a new version, so the history is never
mutated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from sparkd.db.engine import session_scope
from sparkd.db.models import RecipeVersion
from sparkd.errors import NotFoundError


@dataclass
class RecipeVersionView:
    id: int
    name: str
    version: int
    yaml_text: str
    source: str
    note: str | None
    created_at: datetime

    def to_summary(self) -> dict:
        """Without yaml_text — for list responses."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }

    def to_full(self) -> dict:
        return {**self.to_summary(), "yaml_text": self.yaml_text}


def _row_to_view(row: RecipeVersion) -> RecipeVersionView:
    return RecipeVersionView(
        id=row.id,
        name=row.name,
        version=row.version,
        yaml_text=row.yaml_text,
        source=row.source,
        note=row.note,
        created_at=row.created_at,
    )


class RecipeVersionService:
    async def record(
        self,
        name: str,
        yaml_text: str,
        *,
        source: str = "manual",
        note: str | None = None,
    ) -> RecipeVersionView:
        """Append a new version. Skips if the YAML matches the most recent
        version (so callers don't have to dedupe — e.g. an upstream sync that
        hasn't changed)."""
        async with session_scope() as s:
            latest = (
                await s.execute(
                    select(RecipeVersion)
                    .where(RecipeVersion.name == name)
                    .order_by(RecipeVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is not None and latest.yaml_text == yaml_text:
                return _row_to_view(latest)
            next_version = (latest.version + 1) if latest is not None else 1
            row = RecipeVersion(
                name=name,
                version=next_version,
                yaml_text=yaml_text,
                source=source,
                note=note,
            )
            s.add(row)
            await s.flush()
            await s.refresh(row)
            return _row_to_view(row)

    async def list(self, name: str) -> list[RecipeVersionView]:
        async with session_scope() as s:
            rows = (
                await s.execute(
                    select(RecipeVersion)
                    .where(RecipeVersion.name == name)
                    .order_by(RecipeVersion.version.desc())
                )
            ).scalars().all()
            return [_row_to_view(r) for r in rows]

    async def get(self, name: str, version: int) -> RecipeVersionView:
        async with session_scope() as s:
            row = (
                await s.execute(
                    select(RecipeVersion).where(
                        RecipeVersion.name == name,
                        RecipeVersion.version == version,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError(
                    "recipe_version", f"{name}#{version}"
                )
            return _row_to_view(row)

    async def delete_for(self, name: str) -> None:
        async with session_scope() as s:
            rows = (
                await s.execute(
                    select(RecipeVersion).where(RecipeVersion.name == name)
                )
            ).scalars().all()
            for r in rows:
                await s.delete(r)
