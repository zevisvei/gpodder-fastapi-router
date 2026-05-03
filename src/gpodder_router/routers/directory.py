from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from gpodder_router.formats import render_generic
from gpodder_router.schemas.common import Format

router = APIRouter(tags=["Directory"])


@router.get("/api/2/tags/{count}.json")
async def top_tags(count: Annotated[int, Path(ge=1, le=1000)]) -> list[dict[str, object]]:
    """Server-local installations don't have a directory; return empty list."""
    return []


@router.get("/api/2/tag/{tag}/{count}.json")
async def podcasts_for_tag(
    tag: Annotated[str, Path()],
    count: Annotated[int, Path(ge=1, le=1000)],
) -> list[dict[str, object]]:
    return []


@router.get("/api/2/data/podcast.json")
async def podcast_data(url: Annotated[str, Query()]) -> dict[str, object]:
    return {"url": url, "title": url, "description": "", "logo_url": None}


@router.get("/api/2/data/episode.json")
async def episode_data(
    podcast_url: Annotated[str, Query(alias="podcast-url")],
    episode_url: Annotated[str, Query(alias="episode-url")],
) -> dict[str, object]:
    return {
        "podcast_url": podcast_url,
        "url": episode_url,
        "title": episode_url,
        "description": "",
    }


@router.get("/toplist/{number}.{format}")
async def toplist(
    number: Annotated[int, Path(ge=1, le=1000)],
    format: Annotated[Format, Path()],
    jsonp: Annotated[str | None, Query()] = None,
    scale_logo: Annotated[int | None, Query()] = None,
) -> Response:
    return render_generic(format, [], jsonp=jsonp)


@router.get("/search.{format}")
async def search(
    format: Annotated[Format, Path()],
    q: Annotated[str, Query(min_length=1)],
    jsonp: Annotated[str | None, Query()] = None,
    scale_logo: Annotated[int | None, Query()] = None,
) -> Response:
    return render_generic(format, [], jsonp=jsonp)
