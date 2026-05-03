"""Mount gpodder-fastapi-router inside an existing FastAPI app.

This pattern is for projects that already have their own routes,
auth, middleware, and lifespan; the gpodder API becomes one piece of
the larger app instead of the whole server.

Run:
    uv run uvicorn examples.embedded_in_existing_app:app --reload --port 8000

Try:
    GET  /                         -> your own homepage
    GET  /api/hello                -> your own API
    GET  /podsync/clientconfig.json   -> gpodder router under a prefix
    POST /podsync/api/2/auth/<u>/register.json
    GET  /podsync/dashboard/login
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse

from gpodder_router import Database, GPodderConfig, build_router
from gpodder_router.dashboard import build_dashboard_router
from gpodder_router.dashboard.auth import install_redirect_handler

# ---------------------------------------------------------------------------
# 1. Your existing app's stuff
# ---------------------------------------------------------------------------

my_router = APIRouter(prefix="/api", tags=["my-app"])


@my_router.get("/hello")
async def hello() -> dict[str, str]:
    return {"hello": "world"}


def my_api_key(x_api_key: str | None = None) -> str:
    if x_api_key != "secret":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return x_api_key


@my_router.get("/secret", dependencies=[Depends(my_api_key)])
async def secret() -> dict[str, str]:
    return {"data": "private"}


# ---------------------------------------------------------------------------
# 2. gpodder router setup
# ---------------------------------------------------------------------------

gpodder_config = GPodderConfig(
    # Reuse env / .env for everything; override only what we want pinned.
    base_url="http://localhost:8000/podsync",
    dashboard_prefix="/podsync/dashboard",
)
gpodder_db = Database(gpodder_config.database_url, echo=gpodder_config.echo_sql)


# ---------------------------------------------------------------------------
# 3. Combined lifespan that owns BOTH your resources and gpodder's
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ... start your own resources here (e.g. redis, kafka, ML models) ...

    # gpodder schema
    if gpodder_config.create_tables:
        await gpodder_db.create_all()

    # Make config + db available to gpodder dependencies
    app.state.gpodder_config = gpodder_config
    app.state.gpodder_db = gpodder_db

    try:
        yield
    finally:
        await gpodder_db.dispose()
        # ... close your own resources here ...


# ---------------------------------------------------------------------------
# 4. Wire it all into one FastAPI instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="My App + gpodder",
    description="Hosting gpodder-fastapi-router under /podsync",
    lifespan=lifespan,
)

# Your own routes
app.include_router(my_router)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
        <h1>My existing app</h1>
        <ul>
          <li><a href="/api/hello">/api/hello</a></li>
          <li><a href="/podsync/dashboard/login">/podsync/dashboard</a> — gpodder admin</li>
          <li><a href="/podsync/clientconfig.json">/podsync/clientconfig.json</a></li>
          <li><a href="/docs">/docs</a> — combined OpenAPI</li>
        </ul>
    """


# Mount the gpodder API + dashboard under /podsync.
# Both routers share the same FastAPI app, the same OpenAPI doc,
# the same middleware, and the same lifespan.
PODSYNC_PREFIX = "/podsync"
app.include_router(build_router(), prefix=PODSYNC_PREFIX)
install_redirect_handler(app)
app.include_router(
    build_dashboard_router(prefix=gpodder_config.dashboard_prefix),
    # dashboard router already has prefix=/podsync/dashboard built in,
    # so don't double-prefix here.
)
