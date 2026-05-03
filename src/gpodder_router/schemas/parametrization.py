from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _UrlBlock(BaseModel):
    baseurl: str


class ClientConfiguration(BaseModel):
    """Mirrors the /clientconfig.json shape used by mygpo clients."""

    model_config = ConfigDict(populate_by_name=True)

    mygpo: _UrlBlock
    mygpo_feedservice: _UrlBlock = Field(serialization_alias="mygpo-feedservice")
    update_timeout: int
