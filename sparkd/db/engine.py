from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sparkd import paths
from sparkd.db.models import Base

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _alembic_ini_path() -> Path:
    """Locate alembic.ini at the repo root.

    Layout: <root>/sparkd/db/engine.py → parents[2] is <root>.
    For an installed (non-editable) package this would break, but sparkd
    is shipped/run as an editable install so the file is always reachable.
    """
    return Path(__file__).resolve().parents[2] / "alembic.ini"


def _run_migrations_sync(db_path: Path) -> None:
    """Bring the SQLite DB up to alembic head.

    - Fresh DB (no file or no app tables): alembic.upgrade creates everything
      from migration 0001 onward.
    - Legacy DB (app tables exist but no `alembic_version` table — i.e. the DB
      was bootstrapped by an older sparkd that called `create_all` directly):
      stamp head once so the DB enrolls into the migration system. Future
      schema changes apply automatically. We do NOT try to retro-apply
      missing columns; users who upgraded across schema-bumping versions
      need to ALTER once by hand (see docs).
    - Fully migrated DB (alembic_version present): plain `upgrade head` — a
      no-op when already at head.
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(_alembic_ini_path()))
    # The .ini uses sqlite+aiosqlite (matching the runtime engine), but the
    # alembic command runs sync — point it at plain sqlite. env.py also
    # strips +aiosqlite as a belt-and-braces measure.
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    legacy = False
    if db_path.exists():
        with sqlite3.connect(db_path) as raw:
            cur = raw.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('alembic_version', 'boxes')"
            )
            names = {r[0] for r in cur.fetchall()}
        legacy = "boxes" in names and "alembic_version" not in names

    if legacy:
        alembic_command.stamp(cfg, "head")
    alembic_command.upgrade(cfg, "head")


async def init_engine(*, create_all: bool = False, migrate: bool = False) -> None:
    """Initialize the async DB engine.

    Args:
        create_all: Bootstrap missing tables from the current ORM models.
            Used by tests for fast, isolated DB setup. Ignored when
            ``migrate=True`` (alembic owns the schema in that case).
        migrate: Run ``alembic upgrade head`` against the on-disk DB before
            opening connections. Used by the real sparkd boot path so schema
            changes ship via migrations and apply automatically on restart.
            Legacy DBs (no ``alembic_version`` table) are stamped to head
            once so they enroll into the migration system.
    """
    global _engine, _sessionmaker
    paths.ensure()
    db_path = paths.state_db()
    if migrate:
        # Alembic's commands are synchronous; offload to a thread so we don't
        # block the event loop on what is normally a no-op anyway.
        await asyncio.to_thread(_run_migrations_sync, db_path)
    url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(url, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    if create_all and not migrate:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("init_engine() not called")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def shutdown() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
