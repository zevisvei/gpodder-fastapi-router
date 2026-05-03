from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Path, Query

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.schemas.devices import (
    DeviceInfo,
    DeviceUpdateData,
    DeviceUpdatesResponse,
)
from gpodder_router.services import devices as device_service
from gpodder_router.services import episodes as episode_service
from gpodder_router.services import subscriptions as sub_service

router = APIRouter(prefix="/api/2", tags=["Device"])


@router.get("/devices/{username}.json", response_model=list[DeviceInfo])
async def list_devices(
    username: Annotated[str, Path()],
    user: PathUserDep,
    session: SessionDep,
) -> list[DeviceInfo]:
    return await device_service.list_devices(session, user)


@router.post("/devices/{username}/{deviceid}.json", status_code=200)
async def update_device(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    payload: DeviceUpdateData,
    user: PathUserDep,
    session: SessionDep,
) -> dict[str, str]:
    device = await device_service.update_device(session, user, deviceid, payload)
    return {"id": device.deviceid}


@router.get(
    "/updates/{username}/{deviceid}.json",
    response_model=DeviceUpdatesResponse,
    response_model_by_alias=True,
)
async def device_updates(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    since: Annotated[int, Query(ge=0)],
    user: PathUserDep,
    session: SessionDep,
    include_actions: Annotated[bool, Query()] = False,
) -> DeviceUpdatesResponse:
    add_urls, remove_urls, ts = await sub_service.changes_since(
        session, user, deviceid, since
    )
    add_payload = [{"url": u, "title": u, "description": "", "subscribers": 0} for u in add_urls]
    actions: list[dict[str, object]] = []
    if include_actions:
        ep_actions, _ = await episode_service.get_actions(
            session, user, device=deviceid, since=since
        )
        actions = [a.model_dump(exclude_none=True) for a in ep_actions]
    return DeviceUpdatesResponse(
        add=add_payload,
        remove=remove_urls,
        updates=actions,
        timestamp=ts or int(time.time()),
    )
