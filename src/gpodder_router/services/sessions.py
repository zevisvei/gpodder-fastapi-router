from __future__ import annotations

import secrets
import time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Session, User

DEFAULT_TTL = 30 * 24 * 3600  # 30 days


def _now() -> int:
    return int(time.time())


async def create_session(
    session: AsyncSession, user: User, *, ttl: int = DEFAULT_TTL
) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    session.add(
        Session(user_id=user.id, token=token, created=now, expires=now + ttl)
    )
    await session.commit()
    return token


async def lookup(session: AsyncSession, token: str) -> User | None:
    if not token:
        return None
    row = (
        await session.scalars(select(Session).where(Session.token == token))
    ).first()
    if row is None:
        return None
    if row.expires and row.expires < _now():
        await session.delete(row)
        await session.commit()
        return None
    return (
        await session.scalars(select(User).where(User.id == row.user_id))
    ).first()


async def revoke(session: AsyncSession, token: str) -> None:
    if not token:
        return
    await session.execute(delete(Session).where(Session.token == token))
    await session.commit()


async def revoke_for_user(session: AsyncSession, user: User) -> None:
    await session.execute(delete(Session).where(Session.user_id == user.id))
    await session.commit()
