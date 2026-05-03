from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)
    email: str | None = None
