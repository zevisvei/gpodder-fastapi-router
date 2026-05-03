from __future__ import annotations

import json
import re
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import PodcastList, User
from gpodder_router.exceptions import ConflictError, NotFoundError
from gpodder_router.services import users as user_service

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "list"


async def list_for_user(session: AsyncSession, username: str) -> list[PodcastList]:
    user = await user_service.get_user(session, username)
    if user is None:
        raise NotFoundError(f"user {username!r} not found")
    return list(
        (await session.scalars(select(PodcastList).where(PodcastList.user_id == user.id))).all()
    )


async def get(session: AsyncSession, username: str, name: str) -> tuple[PodcastList, list[str]]:
    user = await user_service.get_user(session, username)
    if user is None:
        raise NotFoundError(f"user {username!r} not found")
    plist = (
        await session.scalars(
            select(PodcastList).where(
                PodcastList.user_id == user.id, PodcastList.name == name
            )
        )
    ).first()
    if plist is None:
        raise NotFoundError(f"list {name!r} not found")
    return plist, json.loads(plist.podcasts_json or "[]")


async def create(
    session: AsyncSession, user: User, *, title: str, podcasts: list[str]
) -> PodcastList:
    name = slugify(title)
    existing = (
        await session.scalars(
            select(PodcastList).where(
                PodcastList.user_id == user.id, PodcastList.name == name
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
    session.add(plist)
    await session.commit()
    await session.refresh(plist)
    return plist


async def update(
    session: AsyncSession, user: User, name: str, podcasts: list[str]
) -> PodcastList:
    plist = (
        await session.scalars(
            select(PodcastList).where(
                PodcastList.user_id == user.id, PodcastList.name == name
            )
        )
    ).first()
    if plist is None:
        raise NotFoundError(f"list {name!r} not found")
    plist.podcasts_json = json.dumps(podcasts)
    plist.updated = int(time.time())
    await session.commit()
    await session.refresh(plist)
    return plist


async def delete(session: AsyncSession, user: User, name: str) -> None:
    plist = (
        await session.scalars(
            select(PodcastList).where(
                PodcastList.user_id == user.id, PodcastList.name == name
            )
        )
    ).first()
    if plist is None:
        raise NotFoundError(f"list {name!r} not found")
    await session.delete(plist)
    await session.commit()
