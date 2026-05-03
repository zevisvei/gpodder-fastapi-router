from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SaveSettingsRequest(BaseModel):
    set: dict[str, Any] = Field(default_factory=dict)
    remove: list[str] = Field(default_factory=list)


class SaveSettingsResponse(BaseModel):
    pass
