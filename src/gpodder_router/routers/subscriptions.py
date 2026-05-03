from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request, Response

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.formats import (
    parse_subscription_payload,
    render_subscription_list,
)
from gpodder_router.schemas.common import Format
from gpodder_router.schemas.subscriptions import (
    SubscriptionChanges,
    SubscriptionChangesResponse,
    SubscriptionUploadResponse,
)
from gpodder_router.services import devices as device_service
from gpodder_router.services import subscriptions as sub_service

router = APIRouter(tags=["Subscriptions"])


@router.get("/subscriptions/{username}/{deviceid}.{format}")
async def get_device_subscriptions(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    user: PathUserDep,
    session: SessionDep,
    jsonp: Annotated[str | None, Query()] = None,
) -> Response:
    device = await device_service.get_or_create_device(session, user, deviceid)
    urls = await sub_service.current_for_device(session, user, device.id)
    return render_subscription_list(format, urls, jsonp=jsonp)


@router.put("/subscriptions/{username}/{deviceid}.{format}")
async def upload_device_subscriptions(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    request: Request,
    user: PathUserDep,
    session: SessionDep,
    content_type: Annotated[str, Header()] = "application/json",
) -> Response:
    body = await request.body()
    urls = parse_subscription_payload(content_type, body, format)
    await sub_service.replace_device_subscriptions(session, user, deviceid, urls)
    return Response(status_code=200)


@router.get("/subscriptions/{username}.{format}")
async def get_all_subscriptions(
    username: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    user: PathUserDep,
    session: SessionDep,
    jsonp: Annotated[str | None, Query()] = None,
) -> Response:
    urls = await sub_service.current_for_user(session, user)
    return render_subscription_list(format, urls, jsonp=jsonp)


@router.post(
    "/api/2/subscriptions/{username}/{deviceid}.json",
    response_model=SubscriptionUploadResponse,
)
async def upload_subscription_changes(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    payload: SubscriptionChanges,
    user: PathUserDep,
    session: SessionDep,
) -> SubscriptionUploadResponse:
    timestamp, update_urls = await sub_service.apply_changes(
        session, user, deviceid, payload.add, payload.remove
    )
    return SubscriptionUploadResponse(timestamp=timestamp, update_urls=update_urls)


@router.get(
    "/api/2/subscriptions/{username}/{deviceid}.json",
    response_model=SubscriptionChangesResponse,
)
async def get_subscription_changes(
    username: Annotated[str, Path()],
    deviceid: Annotated[str, Path()],
    since: Annotated[int, Query(ge=0)],
    user: PathUserDep,
    session: SessionDep,
) -> SubscriptionChangesResponse:
    add, remove, ts = await sub_service.changes_since(session, user, deviceid, since)
    return SubscriptionChangesResponse(add=add, remove=remove, timestamp=ts)
