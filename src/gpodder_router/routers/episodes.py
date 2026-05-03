from __future__ import annotations

import json
import os
import time
from pathlib import Path as _Path
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from gpodder_router.deps import PathUserDep, SessionDep
from gpodder_router.schemas.episodes import (
    EpisodeAction,
    EpisodeActionUploadResponse,
    EpisodeActionsResponse,
)
from gpodder_router.services import episodes as episode_service

router = APIRouter(prefix="/api/2/episodes", tags=["Episode Actions"])


def _debug_log_path() -> _Path | None:
    raw = os.environ.get("GPODDER_DEBUG_ACTIONS_FILE")
    if not raw:
        return None
    return _Path(raw).expanduser()


def _debug_dump(username: str, request: Request, body_bytes: bytes) -> None:
    path = _debug_log_path()
    if path is None:
        return
    try:
        try:
            parsed = json.loads(body_bytes.decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        record = {
            "ts": int(time.time()),
            "username": username,
            "client_ip": request.client.host if request.client else None,
            "headers": {k: v for k, v in request.headers.items()},
            "query": dict(request.query_params),
            "body_raw": body_bytes.decode("utf-8", errors="replace"),
            "body_parsed": parsed,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        # debug must never break the request
        pass


@router.post("/{username}.json", response_model=EpisodeActionUploadResponse)
async def upload_episode_actions(
    username: Annotated[str, Path()],
    payload: list[EpisodeAction],
    user: PathUserDep,
    session: SessionDep,
    request: Request,
) -> EpisodeActionUploadResponse:
    body = await request.body()
    _debug_dump(username, request, body)
    timestamp, update_urls = await episode_service.upload(session, user, payload)
    return EpisodeActionUploadResponse(timestamp=timestamp, update_urls=update_urls)


@router.get("/{username}.json", response_model=EpisodeActionsResponse)
async def get_episode_actions(
    username: Annotated[str, Path()],
    user: PathUserDep,
    session: SessionDep,
    podcast: Annotated[str | None, Query()] = None,
    device: Annotated[str | None, Query()] = None,
    since: Annotated[int, Query(ge=0)] = 0,
    aggregated: Annotated[bool, Query()] = False,
) -> EpisodeActionsResponse:
    actions, ts = await episode_service.get_actions(
        session,
        user,
        podcast=podcast,
        device=device,
        since=since,
        aggregated=aggregated,
    )
    return EpisodeActionsResponse(actions=actions, timestamp=ts)
