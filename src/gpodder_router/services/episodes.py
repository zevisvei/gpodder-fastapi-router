from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Device, EpisodeAction as EpisodeActionRow
from gpodder_router.db import SyncGroupMember, User
from gpodder_router.exceptions import NotFoundError
from gpodder_router.schemas.episodes import EpisodeAction, EpisodeActionType
from gpodder_router.services.normalize import normalize_feed_url


def _now() -> int:
    return int(time.time())


def _parse_timestamp(value: str | None) -> int | None:
    """Parse an ISO 8601 timestamp string to epoch seconds.

    Mirrors ``dateutil.parser.parse`` tolerance for the formats AntennaPod and
    desktop gPodder emit (``yyyy-MM-dd'T'HH:mm:ss`` UTC, optionally with
    fractional seconds or timezone). Returns None on parse failure.
    """
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
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


async def _resolve_device(
    session: AsyncSession, user: User, deviceid: str
) -> Device:
    """Strict lookup: 404 if the device is unknown for this user."""
    device = (
        await session.scalars(
            select(Device).where(
                Device.user_id == user.id, Device.deviceid == deviceid
            )
        )
    ).first()
    if device is None:
        raise NotFoundError(f"device {deviceid!r} not found")
    return device


async def _sync_group_device_ids(
    session: AsyncSession, user: User, device: Device
) -> list[str]:
    """Return deviceid strings sharing a sync group with ``device``."""
    member = (
        await session.scalars(
            select(SyncGroupMember).where(
                SyncGroupMember.user_id == user.id,
                SyncGroupMember.device_id == device.id,
            )
        )
    ).first()
    if member is None:
        return [device.deviceid]
    sibling_pks = list(
        (
            await session.scalars(
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
            await session.scalars(
                select(Device.deviceid).where(Device.id.in_(sibling_pks))
            )
        ).all()
    )
    if device.deviceid not in rows:
        rows.append(device.deviceid)
    return rows


async def upload(
    session: AsyncSession,
    user: User,
    actions: Iterable[EpisodeAction],
) -> tuple[int, list[list[str]]]:
    now = _now()
    update_urls: list[list[str]] = []
    for action in actions:
        podcast = normalize_feed_url(action.podcast)
        episode = normalize_feed_url(action.episode)
        if podcast != action.podcast:
            update_urls.append([action.podcast, podcast or ""])
        if episode != action.episode:
            update_urls.append([action.episode, episode or ""])
        if not podcast or not episode:
            continue
        ts_epoch = _parse_timestamp(action.timestamp)
        if ts_epoch is None:
            ts_epoch = now
        session.add(
            EpisodeActionRow(
                user_id=user.id,
                podcast_url=podcast,
                episode_url=episode,
                guid=action.guid,
                device_id=action.device,
                action=action.action.value,
                timestamp=action.timestamp,
                timestamp_epoch=ts_epoch,
                started=action.started,
                position=action.position,
                total=action.total,
                uploaded=now,
            )
        )
    await session.commit()
    return now, update_urls


async def get_actions(
    session: AsyncSession,
    user: User,
    *,
    podcast: str | None = None,
    device: str | None = None,
    since: int = 0,
    aggregated: bool = False,
) -> tuple[list[EpisodeAction], int]:
    stmt = select(EpisodeActionRow).where(EpisodeActionRow.user_id == user.id)
    if since > 0:
        stmt = stmt.where(EpisodeActionRow.timestamp_epoch >= since)
    if podcast:
        stmt = stmt.where(EpisodeActionRow.podcast_url == podcast)
    if device:
        device_row = await _resolve_device(session, user, device)
        device_ids = await _sync_group_device_ids(session, user, device_row)
        stmt = stmt.where(EpisodeActionRow.device_id.in_(device_ids))
    stmt = stmt.order_by(EpisodeActionRow.timestamp_epoch)
    rows = list((await session.scalars(stmt)).all())
    if aggregated:
        keyed: dict[tuple[str, str], EpisodeActionRow] = {}
        for r in rows:
            keyed[(r.podcast_url, r.episode_url)] = r
        rows = list(keyed.values())
    actions = [
        EpisodeAction(
            podcast=r.podcast_url,
            episode=r.episode_url,
            guid=r.guid,
            device=r.device_id,
            action=EpisodeActionType(r.action),
            timestamp=r.timestamp,
            started=r.started,
            position=r.position,
            total=r.total,
        )
        for r in rows
    ]
    if rows:
        last_ts = rows[-1].timestamp_epoch or _now()
    else:
        last_ts = _now()
    return actions, last_ts
