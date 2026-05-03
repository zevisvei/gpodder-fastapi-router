from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.config import GPodderConfig
from gpodder_router.db import Database, User
from gpodder_router.exceptions import AuthenticationError, UsernameMismatchError
from gpodder_router.security import verify_password
from gpodder_router.services import sessions as session_service

SESSION_COOKIE = "sessionid"

_basic = HTTPBasic(auto_error=False)


def get_config(request: Request) -> GPodderConfig:
    cfg = getattr(request.app.state, "gpodder_config", None)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="gpodder router not initialised",
        )
    return cfg


def get_database(request: Request) -> Database:
    db = getattr(request.app.state, "gpodder_db", None)
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="gpodder router not initialised",
        )
    return db


async def get_session(
    db: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ConfigDep = Annotated[GPodderConfig, Depends(get_config)]


async def authenticate(
    session: SessionDep,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)] = None,
    sessionid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """HTTP Basic OR session-cookie auth.

    AntennaPod and gpodder-client perform Basic auth on /login.json once,
    then reuse the session cookie returned by the server for subsequent
    requests. Accept either.
    """
    if credentials is not None:
        user = (
            await session.scalars(
                select(User).where(User.username == credentials.username)
            )
        ).first()
        if user is not None and verify_password(
            credentials.password, user.password_hash
        ):
            return user
    if sessionid:
        user = await session_service.lookup(session, sessionid)
        if user is not None:
            return user
    raise AuthenticationError()


CurrentUserDep = Annotated[User, Depends(authenticate)]


async def authenticated_user_for_path(
    username: Annotated[str, Path()],
    user: CurrentUserDep,
) -> User:
    if user.username.lower() != username.lower():
        raise UsernameMismatchError()
    return user


PathUserDep = Annotated[User, Depends(authenticated_user_for_path)]
