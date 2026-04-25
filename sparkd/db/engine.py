from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sparkd import paths
from sparkd.db.models import Base

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


async def init_engine(*, create_all: bool = False) -> None:
    global _engine, _sessionmaker
    paths.ensure()
    url = f"sqlite+aiosqlite:///{paths.state_db()}"
    _engine = create_async_engine(url, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    if create_all:
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
