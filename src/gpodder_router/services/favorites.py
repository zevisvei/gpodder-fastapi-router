from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Favorite, User
from gpodder_router.schemas.episodes import FavoriteEpisode


def _now_dt() -> datetime:
    return datetime.now(UTC)


class FavoriteStore:
    """Direct DB access for favorite episodes.

    Returns ``datetime`` for ``created`` timestamps.
    """

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def list(self) -> list[FavoriteEpisode]:
        rows = (
            await self.session.scalars(
                select(Favorite)
                .where(Favorite.user_id == self.user.id)
                .order_by(Favorite.created.desc())
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

    async def add(
        self,
        *,
        podcast_url: str,
        episode_url: str,
        title: str | None = None,
        created: datetime | None = None,
    ) -> Favorite:
        existing = (
            await self.session.scalars(
                select(Favorite).where(
                    Favorite.user_id == self.user.id,
                    Favorite.episode_url == episode_url,
                )
            )
        ).first()
        if existing is not None:
            return existing
        ts = created or _now_dt()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        fav = Favorite(
            user_id=self.user.id,
            podcast_url=podcast_url,
            episode_url=episode_url,
            title=title,
            created=int(ts.timestamp()),
        )
        self.session.add(fav)
        await self.session.commit()
        await self.session.refresh(fav)
        return fav


async def list_favorites(
    session: AsyncSession, user: User
) -> list[FavoriteEpisode]:
    return await FavoriteStore(session, user).list()


async def add_favorite(
    session: AsyncSession,
    user: User,
    *,
    podcast_url: str,
    episode_url: str,
    title: str | None = None,
) -> Favorite:
    return await FavoriteStore(session, user).add(
        podcast_url=podcast_url, episode_url=episode_url, title=title
    )
