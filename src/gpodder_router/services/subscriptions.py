from __future__ import annotations

import time
from collections.abc import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Subscription, SyncGroupMember, User
from gpodder_router.exceptions import BadRequestError
from gpodder_router.services import devices as device_service
from gpodder_router.services.normalize import normalize_feed_url


def _now() -> int:
    return int(time.time())


async def _sync_group_device_ids(
    session: AsyncSession, user: User, device_id: int
) -> list[int]:
    """Return device ids in the same sync group as ``device_id``, including itself.

    Devices outside any sync group resolve to a singleton ``[device_id]``.
    """
    member = (
        await session.scalars(
            select(SyncGroupMember).where(
                SyncGroupMember.user_id == user.id,
                SyncGroupMember.device_id == device_id,
            )
        )
    ).first()
    if member is None:
        return [device_id]
    siblings = list(
        (
            await session.scalars(
                select(SyncGroupMember.device_id).where(
                    SyncGroupMember.group_id == member.group_id,
                )
            )
        ).all()
    )
    if device_id not in siblings:
        siblings.append(device_id)
    return siblings


async def current_for_device(
    session: AsyncSession, user: User, device_id: int
) -> list[str]:
    device_ids = await _sync_group_device_ids(session, user, device_id)
    rows = list(
        (
            await session.scalars(
                select(Subscription)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.device_id.in_(device_ids),
                )
                .order_by(Subscription.created)
            )
        ).all()
    )
    # Per podcast across the sync group, the latest tombstone wins.
    latest: dict[str, Subscription] = {}
    for row in rows:
        prev = latest.get(row.podcast_url)
        if prev is None or row.created >= prev.created:
            latest[row.podcast_url] = row
    return [url for url, row in latest.items() if row.deleted == 0]


async def current_for_user(session: AsyncSession, user: User) -> list[str]:
    rows = await session.scalars(
        select(Subscription.podcast_url)
        .where(Subscription.user_id == user.id, Subscription.deleted == 0)
        .order_by(Subscription.created)
    )
    return list(dict.fromkeys(rows.all()))


async def replace_device_subscriptions(
    session: AsyncSession,
    user: User,
    deviceid: str,
    new_urls: Iterable[str],
) -> int:
    """Replace the full subscription set for a device. Returns timestamp."""
    device = await device_service.get_or_create_device(session, user, deviceid)
    now = _now()
    current = set(await current_for_device(session, user, device.id))
    desired: set[str] = set()
    for u in new_urls:
        if not u:
            continue
        norm = normalize_feed_url(u)
        if norm:
            desired.add(norm)

    to_add = desired - current
    to_remove = current - desired

    for url in to_add:
        session.add(
            Subscription(user_id=user.id, device_id=device.id, podcast_url=url, created=now)
        )
    if to_remove:
        existing = (
            await session.scalars(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.device_id == device.id,
                    Subscription.deleted == 0,
                    Subscription.podcast_url.in_(to_remove),
                )
            )
        ).all()
        for sub in existing:
            sub.deleted = now
    await session.commit()
    return now


async def apply_changes(
    session: AsyncSession,
    user: User,
    deviceid: str,
    add: list[str],
    remove: list[str],
) -> tuple[int, list[list[str]]]:
    """Apply add/remove diff. Returns (timestamp, update_urls).

    Mirrors mygpo ``SubscriptionsAPI.update_subscriptions``:
    - filters empty strings from raw inputs
    - 400 if raw add and raw remove share any URL
    - normalizes each URL; emits ``[orig, norm or ""]`` pairs whenever the
      normalized form differs (including when normalization fails and yields None)
    - silently drops removals that collide with adds after normalization
    """
    raw_add = [u for u in add if u]
    raw_remove = [u for u in remove if u]
    conflicts = set(raw_add) & set(raw_remove)
    if conflicts:
        raise BadRequestError(
            "cannot add and remove the same URL in one request: %s"
            % sorted(conflicts)
        )

    device = await device_service.get_or_create_device(session, user, deviceid)
    now = _now()
    update_urls: list[list[str]] = []

    add_norm: list[str | None] = [normalize_feed_url(u) for u in raw_add]
    rem_norm: list[str | None] = [normalize_feed_url(u) for u in raw_remove]
    for orig, norm in zip(raw_add + raw_remove, add_norm + rem_norm):
        if orig != norm:
            update_urls.append([orig, norm or ""])

    add_set: set[str] = {u for u in add_norm if u}
    rem_set: set[str] = {u for u in rem_norm if u and u not in add_set}

    if add_set:
        active = set(await current_for_device(session, user, device.id))
        for url in add_set - active:
            session.add(
                Subscription(
                    user_id=user.id, device_id=device.id, podcast_url=url, created=now
                )
            )
    if rem_set:
        existing = (
            await session.scalars(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.device_id == device.id,
                    Subscription.deleted == 0,
                    Subscription.podcast_url.in_(rem_set),
                )
            )
        ).all()
        for sub in existing:
            sub.deleted = now
    await session.commit()
    return now, update_urls


async def changes_since(
    session: AsyncSession,
    user: User,
    deviceid: str,
    since: int,
) -> tuple[list[str], list[str], int]:
    """Return (added, removed, timestamp) for the device's sync group.

    Changes made on any device that shares a sync group with ``deviceid``
    are reflected here, matching mygpo semantics where subscription state
    is shared across grouped devices.
    """
    device = await device_service.get_or_create_device(session, user, deviceid)
    device_ids = await _sync_group_device_ids(session, user, device.id)
    now = _now()
    rows = (
        await session.scalars(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.device_id.in_(device_ids),
                or_(
                    and_(Subscription.created > since, Subscription.deleted == 0),
                    Subscription.deleted > since,
                ),
            )
        )
    ).all()
    add: list[str] = []
    remove: list[str] = []
    for sub in rows:
        if sub.deleted and sub.deleted > since:
            remove.append(sub.podcast_url)
        elif sub.created > since and sub.deleted == 0:
            add.append(sub.podcast_url)
    return list(dict.fromkeys(add)), list(dict.fromkeys(remove)), now
