from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EpisodeActionType(str, Enum):
    download = "download"
    delete = "delete"
    play = "play"
    new = "new"
    flattr = "flattr"


class EpisodeAction(BaseModel):
    podcast: str
    episode: str
    guid: str | None = None
    device: str | None = None
    action: EpisodeActionType
    timestamp: str | None = None
    started: int | None = None
    position: int | None = None
    total: int | None = None


class EpisodeActionUploadResponse(BaseModel):
    timestamp: int
    update_urls: list[list[str]] = Field(default_factory=list)


class EpisodeActionsResponse(BaseModel):
    actions: list[EpisodeAction] = Field(default_factory=list)
    timestamp: int


class FavoriteEpisode(BaseModel):
    podcast_title: str | None = None
    podcast_url: str
    title: str | None = None
    url: str
