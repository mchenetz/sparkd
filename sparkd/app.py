from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sparkd import logging as sparkd_logging
from sparkd import paths
from sparkd.services import advisor_config
from sparkd.db.engine import init_engine, shutdown
from sparkd.errors import install_handlers
from sparkd.routes.advisor import router as advisor_router
from sparkd.routes.boxes import router as boxes_router
from sparkd.routes.clusters import router as clusters_router
from sparkd.routes.hf import router as hf_router
from sparkd.routes.jobs import router as jobs_router
from sparkd.routes.launches import router as launches_router
from sparkd.routes.mods import router as mods_router
from sparkd.routes.recipes import router as recipes_router
from sparkd.routes.status import router as status_router
from sparkd.routes.ws import router as ws_router
from sparkd.services.advisor import AdvisorService
from sparkd.services.box import BoxService
from sparkd.services.hf_catalog import HFCatalogService
from sparkd.services.jobs import JobRegistry
from sparkd.services.launch import LaunchService
from sparkd.services.library import LibraryService
from sparkd.services.mod import ModService
from sparkd.services.recipe import RecipeService
from sparkd.services.status import StatusService
from sparkd.services.versions import RecipeVersionService
from sparkd.services.upstream import UpstreamService
from sparkd.ssh.pool import SSHPool


_log = logging.getLogger(__name__)

# How often the reconciler ticks. Short enough that the UI flips a launch
# to "healthy" within a few seconds of vLLM coming up; long enough that
# we're not hammering the box's docker daemon.
RECONCILE_INTERVAL_SECONDS = 5.0


async def _launch_reconcile_loop(app: FastAPI) -> None:
    """Persistent state-reconciliation loop.

    Runs throughout sparkd's lifetime, polling each box for the actual
    state of its active launches and writing transitions back to the DB.
    This is what flips a launch from `starting` to `healthy` once vLLM's
    OpenAI endpoint is responsive.

    The loop continues regardless of WebSocket clients, browser tabs, or
    network blips — launches are persistent at the process level (vLLM
    runs via nohup) and at the data level (state.db on disk); this loop
    is what keeps those two layers in sync.
    """
    while True:
        try:
            await app.state.launches.reconcile_active()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — don't let the loop die
            _log.exception("launch reconcile tick failed")
        await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    sparkd_logging.configure()
    await init_engine(migrate=True)
    reconcile_task = asyncio.create_task(_launch_reconcile_loop(app))
    try:
        yield
    finally:
        reconcile_task.cancel()
        try:
            await reconcile_task
        except asyncio.CancelledError:
            pass
        await app.state.pool.close_all()
        await shutdown()


def _mount_spa(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        return
    index = static_dir / "index.html"
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):  # noqa: ARG001
        if index.exists():
            return FileResponse(index)
        return {"error": "frontend not built"}


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
    app.state.hf = HFCatalogService()
    app.state.mods = ModService()
    app.state.recipe_versions = RecipeVersionService()
    app.state.upstream = UpstreamService(
        library=app.state.library,
        mods=app.state.mods,
        versions=app.state.recipe_versions,
    )
    app.state.advisor = AdvisorService(port=advisor_config.build_port())
    # All HTTP API endpoints are namespaced under /api so SPA routes like
    # /recipes/:name don't collide with the API /api/recipes/{name}.
    # WebSocket routes stay at /ws/... — they don't conflict with SPA routes
    # because browsers don't navigate to ws:// URLs.
    app.include_router(boxes_router, prefix="/api")
    app.include_router(clusters_router, prefix="/api")
    app.include_router(recipes_router, prefix="/api")
    app.include_router(launches_router, prefix="/api")
    app.include_router(status_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(hf_router, prefix="/api")
    app.include_router(mods_router, prefix="/api")
    app.include_router(advisor_router, prefix="/api")
    app.include_router(ws_router)

    @app.get("/api/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {
            "db": "ok",
            "ssh_pool_size": len(app.state.pool._conns),
            "sparkd_home": str(paths.root()),
        }

    _mount_spa(app)
    return app
