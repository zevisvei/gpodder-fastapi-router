from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Session, User

DEFAULT_TTL = 30 * 24 * 3600  # 30 days
DEFAULT_TTL_DELTA = timedelta(seconds=DEFAULT_TTL)


def _now_dt() -> datetime:
    return datetime.now(UTC)


class SessionStore:
    """Direct DB access for login sessions.

    Methods accept ``timedelta`` for ``ttl`` and return ``datetime`` for
    timestamps. The HTTP-facing free functions translate epoch ints.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user: User, *, ttl: timedelta = DEFAULT_TTL_DELTA
    ) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        now = _now_dt()
        expires = now + ttl
        self.session.add(
            Session(
                user_id=user.id,
                token=token,
                created=int(now.timestamp()),
                expires=int(expires.timestamp()),
            )
        )
        await self.session.commit()
        return token, expires

    async def lookup(self, token: str) -> User | None:
        if not token:
            return None
        row = (
            await self.session.scalars(
                select(Session).where(Session.token == token)
            )
        ).first()
        if row is None:
            return None
        if row.expires and row.expires < int(_now_dt().timestamp()):
            await self.session.delete(row)
            await self.session.commit()
            return None
        return (
            await self.session.scalars(
                select(User).where(User.id == row.user_id)
            )
        ).first()

    async def revoke(self, token: str) -> None:
        if not token:
            return
        await self.session.execute(
            delete(Session).where(Session.token == token)
        )
        await self.session.commit()

    async def revoke_for_user(self, user: User) -> None:
        await self.session.execute(
            delete(Session).where(Session.user_id == user.id)
        )
        await self.session.commit()


async def create_session(
    session: AsyncSession, user: User, *, ttl: int = DEFAULT_TTL
) -> str:
    token, _ = await SessionStore(session).create(
        user, ttl=timedelta(seconds=ttl)
    )
    return token


async def lookup(session: AsyncSession, token: str) -> User | None:
    return await SessionStore(session).lookup(token)


async def revoke(session: AsyncSession, token: str) -> None:
    await SessionStore(session).revoke(token)


async def revoke_for_user(session: AsyncSession, user: User) -> None:
    await SessionStore(session).revoke_for_user(user)
