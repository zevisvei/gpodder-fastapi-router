from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.config import GPodderConfig
from gpodder_router.db import User
from gpodder_router.deps import SESSION_COOKIE, ConfigDep, SessionDep
from gpodder_router.exceptions import GPodderError
from gpodder_router.services import sessions as session_service


class _RedirectToLogin(GPodderError):
    def __init__(self, prefix: str) -> None:
        super().__init__(status_code=303, detail="login required")
        self._prefix = prefix


async def is_admin(
    config: GPodderConfig, db_session: AsyncSession, username: str
) -> bool:
    if config.admin_usernames:
        return username in config.admin_usernames
    first_username = await db_session.scalar(
        select(User.username).order_by(User.id).limit(1)
    )
    return first_username == username


async def current_user(
    session: SessionDep,
    config: ConfigDep,
    sessionid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    if not sessionid:
        raise _RedirectToLogin(config.dashboard_prefix)
    user = await session_service.lookup(session, sessionid)
    if user is None:
        raise _RedirectToLogin(config.dashboard_prefix)
    return user


async def current_admin(
    session: SessionDep,
    config: ConfigDep,
    sessionid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    user = await current_user(session, config, sessionid)
    if not await is_admin(config, session, user.username):
        raise _RedirectToLogin(config.dashboard_prefix)
    return user


def install_redirect_handler(app) -> None:  # pragma: no cover
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        return

    @app.exception_handler(_RedirectToLogin)
    async def _handle(_, exc: _RedirectToLogin) -> RedirectResponse:
        return RedirectResponse(f"{exc._prefix}/login", status_code=303)


AdminDep = Annotated[User, Depends(current_admin)]
UserDep = Annotated[User, Depends(current_user)]
