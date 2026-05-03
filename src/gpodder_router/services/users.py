from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import User
from gpodder_router.exceptions import ConflictError
from gpodder_router.security import hash_password


async def get_user(session: AsyncSession, username: str) -> User | None:
    return (await session.scalars(select(User).where(User.username == username))).first()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    email: str | None = None,
    bcrypt_rounds: int = 12,
) -> User:
    if await get_user(session, username) is not None:
        raise ConflictError(f"user {username!r} already exists")
    user = User(
        username=username,
        password_hash=hash_password(password, rounds=bcrypt_rounds),
        email=email,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_password(
    session: AsyncSession,
    user: User,
    new_password: str,
    *,
    bcrypt_rounds: int = 12,
) -> None:
    user.password_hash = hash_password(new_password, rounds=bcrypt_rounds)
    await session.commit()
