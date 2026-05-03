from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    desktop = "desktop"
    laptop = "laptop"
    mobile = "mobile"
    server = "server"
    other = "other"


class DeviceUpdateData(BaseModel):
    caption: str | None = None
    type: DeviceType | None = None


class DeviceInfo(BaseModel):
    """List response item.

    AntennaPod parses ``caption`` with ``JSONObject.getString`` (which throws
    on JSON null), so always serialize a string — empty if the user never set
    a caption.
    """

    id: str
    caption: str = ""
    type: DeviceType = DeviceType.other
    subscriptions: int = 0


class DeviceUpdatesResponse(BaseModel):
    add: list[dict[str, Any]] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list, alias="rem")
    updates: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: int

    model_config = {"populate_by_name": True}


class SyncStatusRequest(BaseModel):
    synchronize: list[list[str]] = Field(default_factory=list)
    stop_synchronize: list[str] = Field(default_factory=list, alias="stop-synchronize")

    model_config = {"populate_by_name": True}


class SyncStatus(BaseModel):
    synchronized: list[list[str]] = Field(default_factory=list)
    not_synchronized: list[str] = Field(default_factory=list, alias="not-synchronized")

    model_config = {"populate_by_name": True}
