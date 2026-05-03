from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Device, EpisodeAction as EpisodeActionRow
from gpodder_router.db import SyncGroupMember, User
from gpodder_router.exceptions import NotFoundError
from gpodder_router.schemas.episodes import EpisodeAction, EpisodeActionType
from gpodder_router.services.normalize import normalize_feed_url


def _now() -> int:
    return int(time.time())


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(value: str | None) -> int | None:
    """Parse an ISO 8601 timestamp string to epoch seconds."""
    dt = _parse_timestamp_dt(value)
    if dt is None:
        return None
    return int(dt.timestamp())


def _parse_timestamp_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _format_timestamp(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass(slots=True)
class EpisodeActionInput:
    """Native-typed input for ``EpisodeStore.add_actions``."""

    podcast: str
    episode: str
    action: EpisodeActionType
    guid: str | None = None
    device: str | None = None
    timestamp: datetime | None = None
    started: int | None = None
    position: int | None = None
    total: int | None = None


@dataclass(slots=True)
class EpisodeActionRecord:
    """Native-typed result returned from ``EpisodeStore.list_actions``."""

    podcast: str
    episode: str
    action: EpisodeActionType
    guid: str | None
    device: str | None
    timestamp: datetime | None
    started: int | None
    position: int | None
    total: int | None


class EpisodeStore:
    """Direct DB access to episode actions.

    Accepts native Python types (``datetime``, ``EpisodeActionType``). The HTTP
    service wrappers (``upload``/``get_actions``) translate API payloads to
    these types and delegate here.
    """

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def _resolve_device(self, deviceid: str) -> Device:
        device = (
            await self.session.scalars(
                select(Device).where(
                    Device.user_id == self.user.id, Device.deviceid == deviceid
                )
            )
        ).first()
        if device is None:
            raise NotFoundError(f"device {deviceid!r} not found")
        return device

    async def _sync_group_device_ids(self, device: Device) -> list[str]:
        member = (
            await self.session.scalars(
                select(SyncGroupMember).where(
                    SyncGroupMember.user_id == self.user.id,
                    SyncGroupMember.device_id == device.id,
                )
            )
        ).first()
        if member is None:
            return [device.deviceid]
        sibling_pks = list(
            (
                await self.session.scalars(
                    select(SyncGroupMember.device_id).where(
                        SyncGroupMember.group_id == member.group_id,
                    )
                )
            ).all()
        )
        if not sibling_pks:
            return [device.deviceid]
        rows = list(
            (
                await self.session.scalars(
                    select(Device.deviceid).where(Device.id.in_(sibling_pks))
                )
            ).all()
        )
        if device.deviceid not in rows:
            rows.append(device.deviceid)
        return rows

    async def add_actions(
        self, actions: Iterable[EpisodeActionInput]
    ) -> tuple[datetime, list[tuple[str, str]]]:
        """Insert actions. Returns (server_now, url_normalizations)."""
        now_dt = _now_dt()
        now_epoch = int(now_dt.timestamp())
        update_urls: list[tuple[str, str]] = []
        for action in actions:
            podcast = normalize_feed_url(action.podcast)
            episode = normalize_feed_url(action.episode)
            if podcast != action.podcast:
                update_urls.append((action.podcast, podcast or ""))
            if episode != action.episode:
                update_urls.append((action.episode, episode or ""))
            if not podcast or not episode:
                continue
            if action.timestamp is not None:
                ts_dt = action.timestamp
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=UTC)
                ts_epoch = int(ts_dt.timestamp())
                ts_str = _format_timestamp(ts_dt)
            else:
                ts_epoch = now_epoch
                ts_str = None
            self.session.add(
                EpisodeActionRow(
                    user_id=self.user.id,
                    podcast_url=podcast,
                    episode_url=episode,
                    guid=action.guid,
                    device_id=action.device,
                    action=action.action.value,
                    timestamp=ts_str,
                    timestamp_epoch=ts_epoch,
                    started=action.started,
                    position=action.position,
                    total=action.total,
                    uploaded=now_epoch,
                )
            )
        await self.session.commit()
        return now_dt, update_urls

    async def list_actions(
        self,
        *,
        podcast: str | None = None,
        device: str | None = None,
        since: datetime | None = None,
        aggregated: bool = False,
    ) -> tuple[list[EpisodeActionRecord], datetime]:
        stmt = select(EpisodeActionRow).where(
            EpisodeActionRow.user_id == self.user.id
        )
        if since is not None:
            since_dt = since
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=UTC)
            since_epoch = int(since_dt.timestamp())
            if since_epoch > 0:
                stmt = stmt.where(
                    EpisodeActionRow.timestamp_epoch >= since_epoch
                )
        if podcast:
            stmt = stmt.where(EpisodeActionRow.podcast_url == podcast)
        if device:
            device_row = await self._resolve_device(device)
            device_ids = await self._sync_group_device_ids(device_row)
            stmt = stmt.where(EpisodeActionRow.device_id.in_(device_ids))
        stmt = stmt.order_by(EpisodeActionRow.timestamp_epoch)
        rows = list((await self.session.scalars(stmt)).all())
        if aggregated:
            keyed: dict[tuple[str, str], EpisodeActionRow] = {}
            for r in rows:
                keyed[(r.podcast_url, r.episode_url)] = r
            rows = list(keyed.values())
        records = [
            EpisodeActionRecord(
                podcast=r.podcast_url,
                episode=r.episode_url,
                action=EpisodeActionType(r.action),
                guid=r.guid,
                device=r.device_id,
                timestamp=_parse_timestamp_dt(r.timestamp),
                started=r.started,
                position=r.position,
                total=r.total,
            )
            for r in rows
        ]
        if rows:
            last_epoch = rows[-1].timestamp_epoch or _now()
            last_dt = datetime.fromtimestamp(last_epoch, tz=UTC)
        else:
            last_dt = _now_dt()
        return records, last_dt


async def upload(
    session: AsyncSession,
    user: User,
    actions: Iterable[EpisodeAction],
) -> tuple[int, list[list[str]]]:
    store = EpisodeStore(session, user)
    inputs = [
        EpisodeActionInput(
            podcast=a.podcast,
            episode=a.episode,
            action=a.action,
            guid=a.guid,
            device=a.device,
            timestamp=_parse_timestamp_dt(a.timestamp),
            started=a.started,
            position=a.position,
            total=a.total,
        )
        for a in actions
    ]
    now_dt, update_urls = await store.add_actions(inputs)
    return int(now_dt.timestamp()), [list(p) for p in update_urls]


async def get_actions(
    session: AsyncSession,
    user: User,
    *,
    podcast: str | None = None,
    device: str | None = None,
    since: int = 0,
    aggregated: bool = False,
) -> tuple[list[EpisodeAction], int]:
    store = EpisodeStore(session, user)
    since_dt = (
        datetime.fromtimestamp(since, tz=UTC) if since > 0 else None
    )
    records, last_dt = await store.list_actions(
        podcast=podcast,
        device=device,
        since=since_dt,
        aggregated=aggregated,
    )
    actions = [
        EpisodeAction(
            podcast=r.podcast,
            episode=r.episode,
            guid=r.guid,
            device=r.device,
            action=r.action,
            timestamp=_format_timestamp(r.timestamp),
            started=r.started,
            position=r.position,
            total=r.total,
        )
        for r in records
    ]
    return actions, int(last_dt.timestamp())
