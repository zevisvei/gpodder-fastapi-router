from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Setting, User
from gpodder_router.exceptions import NotFoundError
from gpodder_router.schemas.common import SettingsScope


def _validate_scope_args(
    scope: SettingsScope,
    *,
    podcast: str | None,
    device: str | None,
    episode: str | None,
) -> tuple[str, str]:
    """Return (target, podcast_url) tuple consistent with scope."""
    if scope is SettingsScope.account:
        return "", ""
    if scope is SettingsScope.device:
        if not device:
            raise NotFoundError("`device` query param required for scope=device")
        return device, ""
    if scope is SettingsScope.podcast:
        if not podcast:
            raise NotFoundError("`podcast` query param required for scope=podcast")
        return podcast, ""
    if scope is SettingsScope.episode:
        if not podcast or not episode:
            raise NotFoundError(
                "`podcast` and `episode` query params required for scope=episode"
            )
        return episode, podcast
    raise NotFoundError(f"unknown scope {scope!r}")


class SettingStore:
    """Direct DB access for scoped settings (account/device/podcast/episode)."""

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def get(
        self,
        scope: SettingsScope,
        *,
        podcast: str | None = None,
        device: str | None = None,
        episode: str | None = None,
    ) -> dict[str, Any]:
        target, podcast_url = _validate_scope_args(
            scope, podcast=podcast, device=device, episode=episode
        )
        rows = (
            await self.session.scalars(
                select(Setting).where(
                    Setting.user_id == self.user.id,
                    Setting.scope == scope.value,
                    Setting.target == target,
                    Setting.podcast_url == podcast_url,
                )
            )
        ).all()
        return {r.key: json.loads(r.value) for r in rows}

    async def save(
        self,
        scope: SettingsScope,
        *,
        podcast: str | None = None,
        device: str | None = None,
        episode: str | None = None,
        set_values: dict[str, Any] | None = None,
        remove_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        target, podcast_url = _validate_scope_args(
            scope, podcast=podcast, device=device, episode=episode
        )
        set_values = set_values or {}
        remove_keys = remove_keys or []
        if remove_keys:
            await self.session.execute(
                delete(Setting).where(
                    Setting.user_id == self.user.id,
                    Setting.scope == scope.value,
                    Setting.target == target,
                    Setting.podcast_url == podcast_url,
                    Setting.key.in_(remove_keys),
                )
            )
        for key, value in set_values.items():
            existing = (
                await self.session.scalars(
                    select(Setting).where(
                        Setting.user_id == self.user.id,
                        Setting.scope == scope.value,
                        Setting.target == target,
                        Setting.podcast_url == podcast_url,
                        Setting.key == key,
                    )
                )
            ).first()
            encoded = json.dumps(value)
            if existing is None:
                self.session.add(
                    Setting(
                        user_id=self.user.id,
                        scope=scope.value,
                        target=target,
                        podcast_url=podcast_url,
                        key=key,
                        value=encoded,
                    )
                )
            else:
                existing.value = encoded
        await self.session.commit()
        return await self.get(
            scope, podcast=podcast, device=device, episode=episode
        )


async def get_settings(
    session: AsyncSession,
    user: User,
    scope: SettingsScope,
    *,
    podcast: str | None,
    device: str | None,
    episode: str | None,
) -> dict[str, Any]:
    return await SettingStore(session, user).get(
        scope, podcast=podcast, device=device, episode=episode
    )


async def save_settings(
    session: AsyncSession,
    user: User,
    scope: SettingsScope,
    *,
    podcast: str | None,
    device: str | None,
    episode: str | None,
    set_values: dict[str, Any],
    remove_keys: list[str],
) -> dict[str, Any]:
    return await SettingStore(session, user).save(
        scope,
        podcast=podcast,
        device=device,
        episode=episode,
        set_values=set_values,
        remove_keys=remove_keys,
    )
