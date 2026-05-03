from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import PodcastList, User
from gpodder_router.exceptions import ConflictError, NotFoundError
from gpodder_router.services import users as user_service

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "list"


def _now_dt() -> datetime:
    return datetime.now(UTC)


class ListStore:
    """Direct DB access for podcast lists.

    Some operations are cross-user (lookup by username); pass an explicit
    ``User`` to mutators.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_username(self, username: str) -> list[PodcastList]:
        user = await user_service.UserStore(self.session).get(username)
        if user is None:
            raise NotFoundError(f"user {username!r} not found")
        return list(
            (
                await self.session.scalars(
                    select(PodcastList).where(PodcastList.user_id == user.id)
                )
            ).all()
        )

    async def get(
        self, username: str, name: str
    ) -> tuple[PodcastList, list[str]]:
        user = await user_service.UserStore(self.session).get(username)
        if user is None:
            raise NotFoundError(f"user {username!r} not found")
        plist = (
            await self.session.scalars(
                select(PodcastList).where(
                    PodcastList.user_id == user.id,
                    PodcastList.name == name,
                )
            )
        ).first()
        if plist is None:
            raise NotFoundError(f"list {name!r} not found")
        return plist, json.loads(plist.podcasts_json or "[]")

    async def create(
        self,
        user: User,
        *,
        title: str,
        podcasts: list[str],
    ) -> PodcastList:
        name = slugify(title)
        existing = (
            await self.session.scalars(
                select(PodcastList).where(
                    PodcastList.user_id == user.id,
                    PodcastList.name == name,
                )
            )
        ).first()
        if existing is not None:
            raise ConflictError(f"list {name!r} already exists")
        plist = PodcastList(
            user_id=user.id,
            name=name,
            title=title,
            podcasts_json=json.dumps(podcasts),
        )
        self.session.add(plist)
        await self.session.commit()
        await self.session.refresh(plist)
        return plist

    async def update(
        self,
        user: User,
        name: str,
        podcasts: list[str],
        *,
        updated: datetime | None = None,
    ) -> PodcastList:
        plist = (
            await self.session.scalars(
                select(PodcastList).where(
                    PodcastList.user_id == user.id,
                    PodcastList.name == name,
                )
            )
        ).first()
        if plist is None:
            raise NotFoundError(f"list {name!r} not found")
        plist.podcasts_json = json.dumps(podcasts)
        ts = updated or _now_dt()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        plist.updated = int(ts.timestamp())
        await self.session.commit()
        await self.session.refresh(plist)
        return plist

    async def delete(self, user: User, name: str) -> None:
        plist = (
            await self.session.scalars(
                select(PodcastList).where(
                    PodcastList.user_id == user.id,
                    PodcastList.name == name,
                )
            )
        ).first()
        if plist is None:
            raise NotFoundError(f"list {name!r} not found")
        await self.session.delete(plist)
        await self.session.commit()


async def list_for_user(
    session: AsyncSession, username: str
) -> list[PodcastList]:
    return await ListStore(session).list_for_username(username)


async def get(
    session: AsyncSession, username: str, name: str
) -> tuple[PodcastList, list[str]]:
    return await ListStore(session).get(username, name)


async def create(
    session: AsyncSession, user: User, *, title: str, podcasts: list[str]
) -> PodcastList:
    return await ListStore(session).create(
        user, title=title, podcasts=podcasts
    )


async def update(
    session: AsyncSession, user: User, name: str, podcasts: list[str]
) -> PodcastList:
    return await ListStore(session).update(user, name, podcasts)


async def delete(session: AsyncSession, user: User, name: str) -> None:
    await ListStore(session).delete(user, name)
