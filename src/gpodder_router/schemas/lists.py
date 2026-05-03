from __future__ import annotations

from pydantic import BaseModel, Field


class PodcastListSummary(BaseModel):
    title: str
    name: str
    web: str = ""


class PodcastListInfo(BaseModel):
    name: str
    title: str
    podcasts: list[str] = Field(default_factory=list)
