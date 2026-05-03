from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GPodderConfig(BaseSettings):
    """Runtime configuration for the gpodder router.

    Sources, in priority order (highest wins):

    1. Constructor keyword arguments
    2. Environment variables prefixed ``GPODDER_``
       (e.g. ``GPODDER_DATABASE_URL``)
    3. ``.env`` file in the working directory
    4. Class defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="GPODDER_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./gpodder.db",
        description=(
            "SQLAlchemy async URL. Examples: "
            "sqlite+aiosqlite:///./gpodder.db, "
            "postgresql+asyncpg://user:pw@host/db"
        ),
    )
    create_tables: bool = Field(
        default=True,
        description="If True, create missing tables on startup.",
    )
    echo_sql: bool = Field(default=False)
    allow_registration: bool = Field(
        default=True,
        description="If True, expose POST /api/2/auth/{username}/register.json.",
    )
    base_url: str = Field(
        default="http://localhost:8000",
        description="Public base URL of this server (used in clientconfig).",
    )
    feedservice_url: str = Field(default="http://localhost:8000/feedservice")
    update_timeout: int = Field(default=604800)
    bcrypt_rounds: int = Field(default=12)

    enable_dashboard: bool = Field(
        default=True,
        description="If True, mount the admin dashboard under `dashboard_prefix`.",
    )
    dashboard_prefix: str = Field(default="/dashboard")
    admin_usernames: list[str] = Field(
        default_factory=list,
        description=(
            "Usernames with dashboard access. Empty list = first registered user "
            "becomes admin (bootstrap)."
        ),
    )

    @classmethod
    def from_toml(cls, path: str | Path, **overrides: Any) -> "GPodderConfig":
        """Load config from a TOML file. The ``[gpodder]`` table is honoured;
        any top-level keys are also accepted. Constructor overrides win."""
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        section: dict[str, Any] = dict(data.get("gpodder", {}))
        for key, value in data.items():
            if key != "gpodder" and not isinstance(value, dict):
                section.setdefault(key, value)
        section.update(overrides)
        return cls(**section)
