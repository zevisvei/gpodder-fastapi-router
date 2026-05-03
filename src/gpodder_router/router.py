from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

from gpodder_router.config import GPodderConfig
from gpodder_router.dashboard import build_dashboard_router
from gpodder_router.dashboard.auth import install_redirect_handler
from gpodder_router.db import Database
from gpodder_router.routers import (
    auth,
    devices,
    directory,
    episodes,
    favorites,
    lists,
    parametrization,
    settings as settings_router,
    subscriptions,
    suggestions,
    sync,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


_SUBROUTERS: tuple[APIRouter, ...] = (
    parametrization.router,
    auth.router,
    directory.router,
    suggestions.router,
    devices.router,
    sync.router,
    subscriptions.router,
    episodes.router,
    settings_router.router,
    favorites.router,
    lists.router,
)


def build_router() -> APIRouter:
    """Return a single APIRouter that aggregates every gpodder.net endpoint.

    The router has no prefix; mount it on a FastAPI app or another router.
    Routes already include their own paths (e.g. ``/api/2/...``).
    """
    parent = APIRouter()
    for sub in _SUBROUTERS:
        parent.include_router(sub)
    return parent


def attach(
    app: FastAPI,
    *,
    config: GPodderConfig | None = None,
    database: Database | None = None,
    prefix: str = "",
) -> Database:
    """Attach the gpodder router to an existing FastAPI app.

    Stores the config + Database on ``app.state`` and registers a startup
    hook to create tables (if enabled). Returns the Database instance so
    the caller can close it manually if they don't use a lifespan.
    """
    cfg = config or GPodderConfig()
    db = database or Database(cfg.database_url, echo=cfg.echo_sql)

    app.state.gpodder_config = cfg
    app.state.gpodder_db = db

    if cfg.create_tables:
        @app.on_event("startup")
        async def _startup() -> None:  # pragma: no cover - executed by ASGI
            await db.create_all()

        @app.on_event("shutdown")
        async def _shutdown() -> None:  # pragma: no cover - executed by ASGI
            await db.dispose()

    app.include_router(build_router(), prefix=prefix)
    if cfg.enable_dashboard:
        install_redirect_handler(app)
        app.include_router(
            build_dashboard_router(prefix=cfg.dashboard_prefix), prefix=prefix
        )
    return db


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    *,
    config: GPodderConfig | None = None,
) -> "AsyncIterator[None]":
    """Convenience lifespan that creates schema on startup and disposes on shutdown.

    Usage::

        from gpodder_router import GPodderConfig, build_router, lifespan
        cfg = GPodderConfig()
        app = FastAPI(lifespan=lambda a: lifespan(a, config=cfg))
        app.include_router(build_router())
    """
    cfg = config or GPodderConfig()
    db = Database(cfg.database_url, echo=cfg.echo_sql)
    app.state.gpodder_config = cfg
    app.state.gpodder_db = db
    if cfg.create_tables:
        await db.create_all()
    if cfg.enable_dashboard:
        install_redirect_handler(app)
        app.include_router(build_dashboard_router(prefix=cfg.dashboard_prefix))
    try:
        yield
    finally:
        await db.dispose()
