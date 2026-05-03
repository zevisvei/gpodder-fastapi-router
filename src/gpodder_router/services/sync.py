from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Device, SyncGroup, SyncGroupMember, User
from gpodder_router.exceptions import BadRequestError, NotFoundError


async def get_status(session: AsyncSession, user: User) -> tuple[list[list[str]], list[str]]:
    devices = list(
        (await session.scalars(select(Device).where(Device.user_id == user.id))).all()
    )
    members = list(
        (
            await session.scalars(
                select(SyncGroupMember).where(SyncGroupMember.user_id == user.id)
            )
        ).all()
    )
    by_device: dict[int, str] = {d.id: d.deviceid for d in devices}
    grouped: dict[int, list[str]] = {}
    synced_device_ids: set[int] = set()
    for m in members:
        grouped.setdefault(m.group_id, []).append(by_device.get(m.device_id, ""))
        synced_device_ids.add(m.device_id)
    synchronized = [sorted(d for d in g if d) for g in grouped.values() if len(g) > 1]
    not_sync = [d.deviceid for d in devices if d.id not in synced_device_ids]
    return synchronized, not_sync


async def _strict_lookup(
    session: AsyncSession, user: User, deviceid: str
) -> Device:
    """Mirror mygpo: unknown UID raises 404; never auto-create."""
    row = (
        await session.scalars(
            select(Device).where(
                Device.user_id == user.id, Device.deviceid == deviceid
            )
        )
    ).first()
    if row is None:
        raise NotFoundError(f"device {deviceid!r} not found")
    return row


async def update_groups(
    session: AsyncSession,
    user: User,
    synchronize: list[list[str]],
    stop_synchronize: list[str],
) -> None:
    """Apply mygpo sync-devices semantics.

    - Each group in ``synchronize`` must contain at least two known UIDs;
      otherwise a 400 is raised.
    - Devices in ``synchronize`` and ``stop_synchronize`` must already exist;
      otherwise a 404 is raised. New devices are never auto-created here.
    """
    for group in synchronize:
        if len(group) <= 1:
            raise BadRequestError("at least two devices are needed to sync")
        device_rows = [await _strict_lookup(session, user, did) for did in group]
        existing = (
            await session.scalars(
                select(SyncGroupMember).where(
                    SyncGroupMember.user_id == user.id,
                    SyncGroupMember.device_id.in_([d.id for d in device_rows]),
                )
            )
        ).all()
        for m in existing:
            await session.delete(m)
        await session.flush()
        new_group = SyncGroup(user_id=user.id, active=True)
        session.add(new_group)
        await session.flush()
        for d in device_rows:
            session.add(
                SyncGroupMember(group_id=new_group.id, user_id=user.id, device_id=d.id)
            )

    for did in stop_synchronize:
        device = await _strict_lookup(session, user, did)
        members = (
            await session.scalars(
                select(SyncGroupMember).where(
                    SyncGroupMember.user_id == user.id,
                    SyncGroupMember.device_id == device.id,
                )
            )
        ).all()
        for m in members:
            await session.delete(m)

    await session.commit()
    await _prune_singletons(session, user)


async def _prune_singletons(session: AsyncSession, user: User) -> None:
    groups = list(
        (await session.scalars(select(SyncGroup).where(SyncGroup.user_id == user.id))).all()
    )
    for g in groups:
        members = list(
            (
                await session.scalars(
                    select(SyncGroupMember).where(SyncGroupMember.group_id == g.id)
                )
            ).all()
        )
        if len(members) < 2:
            for m in members:
                await session.delete(m)
            await session.delete(g)
    await session.commit()
