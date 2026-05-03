from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Device, SyncGroup, SyncGroupMember, User
from gpodder_router.exceptions import BadRequestError, NotFoundError


class SyncStore:
    """Direct DB access for device sync groups."""

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def get_status(self) -> tuple[list[list[str]], list[str]]:
        devices = list(
            (
                await self.session.scalars(
                    select(Device).where(Device.user_id == self.user.id)
                )
            ).all()
        )
        members = list(
            (
                await self.session.scalars(
                    select(SyncGroupMember).where(
                        SyncGroupMember.user_id == self.user.id
                    )
                )
            ).all()
        )
        by_device: dict[int, str] = {d.id: d.deviceid for d in devices}
        grouped: dict[int, list[str]] = {}
        synced_device_ids: set[int] = set()
        for m in members:
            grouped.setdefault(m.group_id, []).append(
                by_device.get(m.device_id, "")
            )
            synced_device_ids.add(m.device_id)
        synchronized = [
            sorted(d for d in g if d) for g in grouped.values() if len(g) > 1
        ]
        not_sync = [
            d.deviceid for d in devices if d.id not in synced_device_ids
        ]
        return synchronized, not_sync

    async def _strict_lookup(self, deviceid: str) -> Device:
        row = (
            await self.session.scalars(
                select(Device).where(
                    Device.user_id == self.user.id,
                    Device.deviceid == deviceid,
                )
            )
        ).first()
        if row is None:
            raise NotFoundError(f"device {deviceid!r} not found")
        return row

    async def update_groups(
        self,
        synchronize: list[list[str]],
        stop_synchronize: list[str],
    ) -> None:
        for group in synchronize:
            if len(group) <= 1:
                raise BadRequestError(
                    "at least two devices are needed to sync"
                )
            device_rows = [
                await self._strict_lookup(did) for did in group
            ]
            existing = (
                await self.session.scalars(
                    select(SyncGroupMember).where(
                        SyncGroupMember.user_id == self.user.id,
                        SyncGroupMember.device_id.in_(
                            [d.id for d in device_rows]
                        ),
                    )
                )
            ).all()
            for m in existing:
                await self.session.delete(m)
            await self.session.flush()
            new_group = SyncGroup(user_id=self.user.id, active=True)
            self.session.add(new_group)
            await self.session.flush()
            for d in device_rows:
                self.session.add(
                    SyncGroupMember(
                        group_id=new_group.id,
                        user_id=self.user.id,
                        device_id=d.id,
                    )
                )

        for did in stop_synchronize:
            device = await self._strict_lookup(did)
            members = (
                await self.session.scalars(
                    select(SyncGroupMember).where(
                        SyncGroupMember.user_id == self.user.id,
                        SyncGroupMember.device_id == device.id,
                    )
                )
            ).all()
            for m in members:
                await self.session.delete(m)

        await self.session.commit()
        await self._prune_singletons()

    async def _prune_singletons(self) -> None:
        groups = list(
            (
                await self.session.scalars(
                    select(SyncGroup).where(SyncGroup.user_id == self.user.id)
                )
            ).all()
        )
        for g in groups:
            members = list(
                (
                    await self.session.scalars(
                        select(SyncGroupMember).where(
                            SyncGroupMember.group_id == g.id
                        )
                    )
                ).all()
            )
            if len(members) < 2:
                for m in members:
                    await self.session.delete(m)
                await self.session.delete(g)
        await self.session.commit()


async def get_status(
    session: AsyncSession, user: User
) -> tuple[list[list[str]], list[str]]:
    return await SyncStore(session, user).get_status()


async def update_groups(
    session: AsyncSession,
    user: User,
    synchronize: list[list[str]],
    stop_synchronize: list[str],
) -> None:
    await SyncStore(session, user).update_groups(synchronize, stop_synchronize)
