from __future__ import annotations

import base64
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from gpodder_router import Database, GPodderConfig, build_router
from gpodder_router.dashboard import build_dashboard_router
from gpodder_router.dashboard.auth import install_redirect_handler
from gpodder_router.services import users as user_service


@pytest_asyncio.fixture
async def app(tmp_path) -> AsyncIterator[FastAPI]:
    db_path = tmp_path / "gp.db"
    cfg = GPodderConfig(
        _env_file=None,  # ignore developer .env during tests
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
        create_tables=False,
        bcrypt_rounds=4,  # fast tests
        admin_usernames=[],
        enable_dashboard=True,
    )
    db = Database(cfg.database_url, echo=False)
    await db.create_all()

    application = FastAPI()
    application.state.gpodder_config = cfg
    application.state.gpodder_db = db
    application.include_router(build_router())
    install_redirect_handler(application)
    application.include_router(build_dashboard_router(prefix=cfg.dashboard_prefix))

    # seed a user
    async with db.session() as session:
        await user_service.create_user(
            session, username="alice", password="secret", bcrypt_rounds=4
        )

    try:
        yield application
    finally:
        await db.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def alice_auth() -> dict[str, str]:
    creds = base64.b64encode(b"alice:secret").decode("ascii")
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture
def bad_auth() -> dict[str, str]:
    creds = base64.b64encode(b"alice:wrong").decode("ascii")
    return {"Authorization": f"Basic {creds}"}
