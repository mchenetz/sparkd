from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sparkd.db.engine import init_engine, shutdown
from sparkd.errors import install_handlers
from sparkd.routes.boxes import router as boxes_router
from sparkd.services.box import BoxService
from sparkd.services.jobs import JobRegistry
from sparkd.services.library import LibraryService
from sparkd.ssh.pool import SSHPool


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_engine(create_all=True)
    try:
        yield
    finally:
        await app.state.pool.close_all()
        await shutdown()


def build_app() -> FastAPI:
    app = FastAPI(title="sparkd", lifespan=_lifespan)
    install_handlers(app)
    pool = SSHPool()
    app.state.pool = pool
    app.state.boxes = BoxService(pool=pool)
    app.state.library = LibraryService()
    app.state.jobs = JobRegistry()
    app.include_router(boxes_router)
    return app
