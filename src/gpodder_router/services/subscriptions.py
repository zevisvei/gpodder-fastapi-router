from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Subscription, SyncGroupMember, User
from gpodder_router.exceptions import BadRequestError
from gpodder_router.services import devices as device_service
from gpodder_router.services.normalize import normalize_feed_url


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _to_dt(epoch_or_dt: int | datetime) -> datetime:
    if isinstance(epoch_or_dt, datetime):
        if epoch_or_dt.tzinfo is None:
            return epoch_or_dt.replace(tzinfo=UTC)
        return epoch_or_dt
    return datetime.fromtimestamp(epoch_or_dt, tz=UTC)


class SubscriptionStore:
    """Direct DB access for podcast subscriptions.

    Returns ``datetime`` for timestamps. The HTTP-facing free functions in
    this module expose epoch ints for the gpodder API.
    """

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def _sync_group_device_ids(self, device_id: int) -> list[int]:
        member = (
            await self.session.scalars(
                select(SyncGroupMember).where(
                    SyncGroupMember.user_id == self.user.id,
                    SyncGroupMember.device_id == device_id,
                )
            )
        ).first()
        if member is None:
            return [device_id]
        siblings = list(
            (
                await self.session.scalars(
                    select(SyncGroupMember.device_id).where(
                        SyncGroupMember.group_id == member.group_id,
                    )
                )
            ).all()
        )
        if device_id not in siblings:
            siblings.append(device_id)
        return siblings

    async def current_for_device(self, device_id: int) -> list[str]:
        device_ids = await self._sync_group_device_ids(device_id)
        rows = list(
            (
                await self.session.scalars(
                    select(Subscription)
                    .where(
                        Subscription.user_id == self.user.id,
                        Subscription.device_id.in_(device_ids),
                    )
                    .order_by(Subscription.created)
                )
            ).all()
        )
        latest: dict[str, Subscription] = {}
        for row in rows:
            prev = latest.get(row.podcast_url)
            if prev is None or row.created >= prev.created:
                latest[row.podcast_url] = row
        return [url for url, row in latest.items() if row.deleted == 0]

    async def current_for_user(self) -> list[str]:
        rows = await self.session.scalars(
            select(Subscription.podcast_url)
            .where(
                Subscription.user_id == self.user.id,
                Subscription.deleted == 0,
            )
            .order_by(Subscription.created)
        )
        return list(dict.fromkeys(rows.all()))

    async def replace_device_subscriptions(
        self, deviceid: str, new_urls: Iterable[str]
    ) -> datetime:
        device = await device_service.DeviceStore(
            self.session, self.user
        ).get_or_create(deviceid)
        now_dt = _now_dt()
        now_epoch = int(now_dt.timestamp())
        current = set(await self.current_for_device(device.id))
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
            self.session.add(
                Subscription(
                    user_id=self.user.id,
                    device_id=device.id,
                    podcast_url=url,
                    created=now_epoch,
                )
            )
        if to_remove:
            existing = (
                await self.session.scalars(
                    select(Subscription).where(
                        Subscription.user_id == self.user.id,
                        Subscription.device_id == device.id,
                        Subscription.deleted == 0,
                        Subscription.podcast_url.in_(to_remove),
                    )
                )
            ).all()
            for sub in existing:
                sub.deleted = now_epoch
        await self.session.commit()
        return now_dt

    async def apply_changes(
        self,
        deviceid: str,
        add: list[str],
        remove: list[str],
    ) -> tuple[datetime, list[tuple[str, str]]]:
        raw_add = [u for u in add if u]
        raw_remove = [u for u in remove if u]
        conflicts = set(raw_add) & set(raw_remove)
        if conflicts:
            raise BadRequestError(
                "cannot add and remove the same URL in one request: %s"
                % sorted(conflicts)
            )

        device = await device_service.DeviceStore(
            self.session, self.user
        ).get_or_create(deviceid)
        now_dt = _now_dt()
        now_epoch = int(now_dt.timestamp())
        update_urls: list[tuple[str, str]] = []

        add_norm: list[str | None] = [
            normalize_feed_url(u) for u in raw_add
        ]
        rem_norm: list[str | None] = [
            normalize_feed_url(u) for u in raw_remove
        ]
        for orig, norm in zip(raw_add + raw_remove, add_norm + rem_norm):
            if orig != norm:
                update_urls.append((orig, norm or ""))

        add_set: set[str] = {u for u in add_norm if u}
        rem_set: set[str] = {
            u for u in rem_norm if u and u not in add_set
        }

        if add_set:
            active = set(await self.current_for_device(device.id))
            for url in add_set - active:
                self.session.add(
                    Subscription(
                        user_id=self.user.id,
                        device_id=device.id,
                        podcast_url=url,
                        created=now_epoch,
                    )
                )
        if rem_set:
            existing = (
                await self.session.scalars(
                    select(Subscription).where(
                        Subscription.user_id == self.user.id,
                        Subscription.device_id == device.id,
                        Subscription.deleted == 0,
                        Subscription.podcast_url.in_(rem_set),
                    )
                )
            ).all()
            for sub in existing:
                sub.deleted = now_epoch
        await self.session.commit()
        return now_dt, update_urls

    async def changes_since(
        self,
        deviceid: str,
        since: datetime,
    ) -> tuple[list[str], list[str], datetime]:
        device = await device_service.DeviceStore(
            self.session, self.user
        ).get_or_create(deviceid)
        device_ids = await self._sync_group_device_ids(device.id)
        since_epoch = int(_to_dt(since).timestamp())
        now_dt = _now_dt()
        rows = (
            await self.session.scalars(
                select(Subscription).where(
                    Subscription.user_id == self.user.id,
                    Subscription.device_id.in_(device_ids),
                    or_(
                        and_(
                            Subscription.created > since_epoch,
                            Subscription.deleted == 0,
                        ),
                        Subscription.deleted > since_epoch,
                    ),
                )
            )
        ).all()
        add: list[str] = []
        remove: list[str] = []
        for sub in rows:
            if sub.deleted and sub.deleted > since_epoch:
                remove.append(sub.podcast_url)
            elif sub.created > since_epoch and sub.deleted == 0:
                add.append(sub.podcast_url)
        return (
            list(dict.fromkeys(add)),
            list(dict.fromkeys(remove)),
            now_dt,
        )


async def current_for_device(
    session: AsyncSession, user: User, device_id: int
) -> list[str]:
    return await SubscriptionStore(session, user).current_for_device(
        device_id
    )


async def current_for_user(
    session: AsyncSession, user: User
) -> list[str]:
    return await SubscriptionStore(session, user).current_for_user()


async def replace_device_subscriptions(
    session: AsyncSession,
    user: User,
    deviceid: str,
    new_urls: Iterable[str],
) -> int:
    dt = await SubscriptionStore(session, user).replace_device_subscriptions(
        deviceid, new_urls
    )
    return int(dt.timestamp())


async def apply_changes(
    session: AsyncSession,
    user: User,
    deviceid: str,
    add: list[str],
    remove: list[str],
) -> tuple[int, list[list[str]]]:
    dt, update_urls = await SubscriptionStore(session, user).apply_changes(
        deviceid, add, remove
    )
    return int(dt.timestamp()), [list(p) for p in update_urls]


async def changes_since(
    session: AsyncSession,
    user: User,
    deviceid: str,
    since: int,
) -> tuple[list[str], list[str], int]:
    add, remove, dt = await SubscriptionStore(session, user).changes_since(
        deviceid, datetime.fromtimestamp(since, tz=UTC)
    )
    return add, remove, int(dt.timestamp())
