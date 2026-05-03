from __future__ import annotations

from pydantic import BaseModel, Field


class SubscriptionChanges(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class SubscriptionUploadResponse(BaseModel):
    timestamp: int
    update_urls: list[list[str]] = Field(default_factory=list)


class SubscriptionChangesResponse(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    timestamp: int
