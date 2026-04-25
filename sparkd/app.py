from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sparkd.db.engine import init_engine, shutdown
from sparkd.errors import install_handlers
from sparkd.routes.boxes import router as boxes_router
from sparkd.routes.jobs import router as jobs_router
from sparkd.routes.launches import router as launches_router
from sparkd.routes.recipes import router as recipes_router
from sparkd.routes.status import router as status_router
from sparkd.routes.ws import router as ws_router
from sparkd.services.box import BoxService
from sparkd.services.jobs import JobRegistry
from sparkd.services.launch import LaunchService
from sparkd.services.library import LibraryService
from sparkd.services.recipe import RecipeService
from sparkd.services.status import StatusService
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
    app.state.recipes = RecipeService(
        library=app.state.library, boxes=app.state.boxes, pool=pool
    )
    app.state.launches = LaunchService(
        library=app.state.library,
        boxes=app.state.boxes,
        recipes=app.state.recipes,
        pool=pool,
    )
    app.state.status = StatusService(boxes=app.state.boxes, pool=pool)
    app.include_router(boxes_router)
    app.include_router(recipes_router)
    app.include_router(launches_router)
    app.include_router(status_router)
    app.include_router(jobs_router)
    app.include_router(ws_router)
    return app
