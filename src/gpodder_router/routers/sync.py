from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.schemas.devices import SyncStatus, SyncStatusRequest
from gpodder_router.services import sync as sync_service

router = APIRouter(prefix="/api/2/sync-devices", tags=["Device Synchronization"])


@router.get("/{username}.json", response_model=SyncStatus, response_model_by_alias=True)
async def get_sync_status(
    username: Annotated[str, Path()],
    user: PathUserDep,
    session: SessionDep,
) -> SyncStatus:
    synchronized, not_sync = await sync_service.get_status(session, user)
    return SyncStatus(synchronized=synchronized, not_synchronized=not_sync)


@router.post("/{username}.json", response_model=SyncStatus, response_model_by_alias=True)
async def update_sync_status(
    username: Annotated[str, Path()],
    payload: SyncStatusRequest,
    user: PathUserDep,
    session: SessionDep,
) -> SyncStatus:
    await sync_service.update_groups(
        session, user, payload.synchronize, payload.stop_synchronize
    )
    synchronized, not_sync = await sync_service.get_status(session, user)
    return SyncStatus(synchronized=synchronized, not_synchronized=not_sync)
