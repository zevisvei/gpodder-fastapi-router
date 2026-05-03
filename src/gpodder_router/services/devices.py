from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gpodder_router.db import Device, Subscription, User
from gpodder_router.exceptions import NotFoundError
from gpodder_router.schemas.devices import DeviceInfo, DeviceType, DeviceUpdateData

_DEVICEID_RE = re.compile(r"^[\w.\-]+$")


def validate_deviceid(deviceid: str) -> str:
    if not _DEVICEID_RE.match(deviceid):
        raise NotFoundError(f"invalid device id: {deviceid!r}")
    return deviceid


class DeviceStore:
    """Direct DB access for devices owned by a user.

    Operates on ORM ``Device`` rows. The HTTP-facing free functions in
    this module are thin wrappers around this class.
    """

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def get_or_create(self, deviceid: str) -> Device:
        validate_deviceid(deviceid)
        device = (
            await self.session.scalars(
                select(Device).where(
                    Device.user_id == self.user.id,
                    Device.deviceid == deviceid,
                )
            )
        ).first()
        if device is None:
            device = Device(
                user_id=self.user.id,
                deviceid=deviceid,
                type=DeviceType.other.value,
            )
            self.session.add(device)
            await self.session.commit()
            await self.session.refresh(device)
        return device

    async def get(self, deviceid: str) -> Device:
        device = (
            await self.session.scalars(
                select(Device).where(
                    Device.user_id == self.user.id,
                    Device.deviceid == deviceid,
                )
            )
        ).first()
        if device is None:
            raise NotFoundError(f"device {deviceid!r} not found")
        return device

    async def update(
        self, deviceid: str, data: DeviceUpdateData
    ) -> Device:
        device = await self.get_or_create(deviceid)
        if data.caption is not None:
            device.caption = data.caption
        if data.type is not None:
            device.type = data.type.value
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def list_with_counts(self) -> list[DeviceInfo]:
        devices = list(
            (
                await self.session.scalars(
                    select(Device).where(Device.user_id == self.user.id)
                )
            ).all()
        )
        if not devices:
            return []
        counts: dict[int, int] = {}
        rows = await self.session.execute(
            select(Subscription.device_id, func.count(Subscription.id))
            .where(
                Subscription.user_id == self.user.id,
                Subscription.deleted == 0,
            )
            .group_by(Subscription.device_id)
        )
        for device_id, count in rows.all():
            counts[device_id] = int(count)
        return [
            DeviceInfo(
                id=d.deviceid,
                caption=d.caption or "",
                type=DeviceType(d.type)
                if d.type in DeviceType._value2member_map_
                else DeviceType.other,
                subscriptions=counts.get(d.id, 0),
            )
            for d in devices
        ]


async def get_or_create_device(
    session: AsyncSession, user: User, deviceid: str
) -> Device:
    return await DeviceStore(session, user).get_or_create(deviceid)


async def get_device(
    session: AsyncSession, user: User, deviceid: str
) -> Device:
    return await DeviceStore(session, user).get(deviceid)


async def update_device(
    session: AsyncSession,
    user: User,
    deviceid: str,
    data: DeviceUpdateData,
) -> Device:
    return await DeviceStore(session, user).update(deviceid, data)


async def list_devices(session: AsyncSession, user: User) -> list[DeviceInfo]:
    return await DeviceStore(session, user).list_with_counts()
