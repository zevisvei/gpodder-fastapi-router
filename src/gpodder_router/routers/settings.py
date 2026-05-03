from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.schemas.common import SettingsScope
from gpodder_router.schemas.settings import SaveSettingsRequest
from gpodder_router.services import settings as settings_service

router = APIRouter(prefix="/api/2/settings", tags=["Settings"])


@router.get("/{username}/{scope}.json")
async def get_settings(
    username: Annotated[str, Path()],
    scope: Annotated[SettingsScope, Path()],
    user: PathUserDep,
    session: SessionDep,
    podcast: Annotated[str | None, Query()] = None,
    device: Annotated[str | None, Query()] = None,
    episode: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return await settings_service.get_settings(
        session, user, scope, podcast=podcast, device=device, episode=episode
    )


@router.post("/{username}/{scope}.json")
async def save_settings(
    username: Annotated[str, Path()],
    scope: Annotated[SettingsScope, Path()],
    payload: SaveSettingsRequest,
    user: PathUserDep,
    session: SessionDep,
    podcast: Annotated[str | None, Query()] = None,
    device: Annotated[str | None, Query()] = None,
    episode: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return await settings_service.save_settings(
        session,
        user,
        scope,
        podcast=podcast,
        device=device,
        episode=episode,
        set_values=payload.set,
        remove_keys=payload.remove,
    )
