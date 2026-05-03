from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.schemas.episodes import FavoriteEpisode
from gpodder_router.services import favorites as fav_service

router = APIRouter(prefix="/api/2/favorites", tags=["Favorites"])


@router.get("/{username}.json", response_model=list[FavoriteEpisode])
async def list_favorites(
    username: Annotated[str, Path()],
    user: PathUserDep,
    session: SessionDep,
) -> list[FavoriteEpisode]:
    return await fav_service.list_favorites(session, user)
