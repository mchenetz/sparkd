from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sparkd import logging as sparkd_logging
from sparkd import paths
from sparkd import secrets as sparkd_secrets
from sparkd.advisor import AnthropicAdapter
from sparkd.db.engine import init_engine, shutdown
from sparkd.errors import install_handlers
from sparkd.routes.advisor import router as advisor_router
from sparkd.routes.boxes import router as boxes_router
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
from sparkd.services.upstream import UpstreamService
from sparkd.ssh.pool import SSHPool


@asynccontextmanager
async def _lifespan(app: FastAPI):
    sparkd_logging.configure()
    await init_engine(create_all=True)
    try:
        yield
    finally:
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
    app.state.upstream = UpstreamService(library=app.state.library)
    api_key = sparkd_secrets.get_secret("anthropic_api_key") or ""
    port = AnthropicAdapter(api_key=api_key) if api_key else None
    app.state.advisor = AdvisorService(port=port)
    app.include_router(boxes_router)
    app.include_router(recipes_router)
    app.include_router(launches_router)
    app.include_router(status_router)
    app.include_router(jobs_router)
    app.include_router(hf_router)
    app.include_router(mods_router)
    app.include_router(advisor_router)
    app.include_router(ws_router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {
            "db": "ok",
            "ssh_pool_size": len(app.state.pool._conns),
            "sparkd_home": str(paths.root()),
        }

    _mount_spa(app)
    return app
