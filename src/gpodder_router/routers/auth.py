from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Path, Response, status

from gpodder_router.deps import SESSION_COOKIE, ConfigDep, PathUserDep, SessionDep
from gpodder_router.exceptions import UsernameMismatchError
from gpodder_router.exceptions import ConflictError
from gpodder_router.schemas.users import RegisterRequest
from gpodder_router.services import sessions as session_service
from gpodder_router.services import users as user_service

router = APIRouter(prefix="/api/2/auth", tags=["Authentication"])


@router.post("/{username}/login.json", status_code=status.HTTP_200_OK)
async def login(
    user: PathUserDep,
    session: SessionDep,
    response: Response,
) -> Response:
    token = await session_service.create_session(session, user)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=session_service.DEFAULT_TTL,
    )
    return Response(status_code=status.HTTP_200_OK, headers=dict(response.headers))


@router.post("/{username}/logout.json", status_code=status.HTTP_200_OK)
async def logout(
    username: Annotated[str, Path()],
    session: SessionDep,
    response: Response,
    sessionid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    """Mygpo logout requires no authentication; idempotently clear cookie + session."""
    if sessionid:
        existing = await session_service.lookup(session, sessionid)
        if existing is not None and existing.username != username:
            raise UsernameMismatchError()
        await session_service.revoke(session, sessionid)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Response(status_code=status.HTTP_200_OK, headers=dict(response.headers))


@router.post("/{username}/register.json", status_code=status.HTTP_201_CREATED)
async def register(
    username: Annotated[str, Path()],
    payload: RegisterRequest,
    session: SessionDep,
    config: ConfigDep,
) -> dict[str, str]:
    """Extension to mygpo: optional self-service registration.

    Disabled by setting ``allow_registration=False`` on the config.
    """
    if not config.allow_registration:
        raise ConflictError("registration disabled")
    await user_service.create_user(
        session,
        username=username,
        password=payload.password,
        email=payload.email,
        bcrypt_rounds=config.bcrypt_rounds,
    )
    return {"username": username}
