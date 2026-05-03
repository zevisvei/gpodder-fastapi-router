from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import User
from gpodder_router.exceptions import ConflictError
from gpodder_router.security import hash_password


class UserStore:
    """Direct DB access for user accounts.

    Bypasses the HTTP API. Construct with an ``AsyncSession`` and call
    methods directly from library/CLI code.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, username: str) -> User | None:
        return (
            await self.session.scalars(
                select(User).where(User.username == username)
            )
        ).first()

    async def create(
        self,
        *,
        username: str,
        password: str,
        email: str | None = None,
        bcrypt_rounds: int = 12,
    ) -> User:
        if await self.get(username) is not None:
            raise ConflictError(f"user {username!r} already exists")
        user = User(
            username=username,
            password_hash=hash_password(password, rounds=bcrypt_rounds),
            email=email,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def set_password(
        self,
        user: User,
        new_password: str,
        *,
        bcrypt_rounds: int = 12,
    ) -> None:
        user.password_hash = hash_password(new_password, rounds=bcrypt_rounds)
        await self.session.commit()


async def get_user(session: AsyncSession, username: str) -> User | None:
    return await UserStore(session).get(username)


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    email: str | None = None,
    bcrypt_rounds: int = 12,
) -> User:
    return await UserStore(session).create(
        username=username,
        password=password,
        email=email,
        bcrypt_rounds=bcrypt_rounds,
    )


async def set_password(
    session: AsyncSession,
    user: User,
    new_password: str,
    *,
    bcrypt_rounds: int = 12,
) -> None:
    await UserStore(session).set_password(
        user, new_password, bcrypt_rounds=bcrypt_rounds
    )
