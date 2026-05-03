from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Favorite, User
from gpodder_router.schemas.episodes import FavoriteEpisode


async def list_favorites(session: AsyncSession, user: User) -> list[FavoriteEpisode]:
    rows = (
        await session.scalars(
            select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created.desc())
        )
    ).all()
    return [
        FavoriteEpisode(
            podcast_url=r.podcast_url,
            url=r.episode_url,
            title=r.title,
        )
        for r in rows
    ]


async def add_favorite(
    session: AsyncSession,
    user: User,
    *,
    podcast_url: str,
    episode_url: str,
    title: str | None = None,
) -> Favorite:
    existing = (
        await session.scalars(
            select(Favorite).where(
                Favorite.user_id == user.id, Favorite.episode_url == episode_url
            )
        )
    ).first()
    if existing is not None:
        return existing
    fav = Favorite(
        user_id=user.id,
        podcast_url=podcast_url,
        episode_url=episode_url,
        title=title,
        created=int(time.time()),
    )
    session.add(fav)
    await session.commit()
    await session.refresh(fav)
    return fav
