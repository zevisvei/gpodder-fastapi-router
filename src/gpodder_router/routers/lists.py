from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response, status

from gpodder_router.deps import ConfigDep, PathUserDep, SessionDep
from gpodder_router.formats import parse_subscription_payload, render_subscription_list
from gpodder_router.schemas.common import Format
from gpodder_router.schemas.lists import PodcastListSummary
from gpodder_router.services import lists as list_service
from gpodder_router.services.normalize import normalize_feed_url

router = APIRouter(prefix="/api/2/lists", tags=["Podcast Lists"])


def _list_web_url(base_url: str, username: str, name: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/list/{username}/{name}"


@router.get("/{username}.json", response_model=list[PodcastListSummary])
async def get_user_lists(
    username: Annotated[str, Path()],
    session: SessionDep,
    config: ConfigDep,
) -> list[PodcastListSummary]:
    rows = await list_service.list_for_user(session, username)
    return [
        PodcastListSummary(
            title=r.title,
            name=r.name,
            web=_list_web_url(config.base_url, username, r.name),
        )
        for r in rows
    ]


@router.post("/{username}/create.{format}", status_code=status.HTTP_201_CREATED)
async def create_list(
    username: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    title: Annotated[str, Query(min_length=1)],
    request: Request,
    user: PathUserDep,
    session: SessionDep,
) -> Response:
    body = await request.body()
    raw_urls = parse_subscription_payload(
        request.headers.get("content-type", "application/json"), body, format
    )
    podcasts = [u for u in (normalize_feed_url(r) for r in raw_urls) if u]
    plist = await list_service.create(session, user, title=title, podcasts=podcasts)
    location = f"/api/2/lists/{username}/list/{plist.name}.{format.value}"
    return Response(
        status_code=status.HTTP_201_CREATED,
        headers={"Location": location},
    )


@router.get("/{username}/list/{listname}.{format}")
async def get_list(
    username: Annotated[str, Path()],
    listname: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    session: SessionDep,
) -> Response:
    plist, podcasts = await list_service.get(session, username, listname)
    return render_subscription_list(format, podcasts, title=plist.title)


@router.put("/{username}/list/{listname}.{format}", status_code=status.HTTP_204_NO_CONTENT)
async def update_list(
    username: Annotated[str, Path()],
    listname: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    request: Request,
    user: PathUserDep,
    session: SessionDep,
) -> Response:
    body = await request.body()
    raw_urls = parse_subscription_payload(
        request.headers.get("content-type", "application/json"), body, format
    )
    podcasts = [u for u in (normalize_feed_url(r) for r in raw_urls) if u]
    await list_service.update(session, user, listname, podcasts)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{username}/list/{listname}.{format}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(
    username: Annotated[str, Path()],
    listname: Annotated[str, Path()],
    format: Annotated[Format, Path()],
    user: PathUserDep,
    session: SessionDep,
) -> Response:
    await list_service.delete(session, user, listname)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
