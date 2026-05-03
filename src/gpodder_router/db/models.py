from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gpodder_router.db.base import Base


def _now() -> int:
    return int(time.time())


class User(Base):
    __tablename__ = "gpodder_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created: Mapped[int] = mapped_column(BigInteger, default=_now)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "gpodder_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created: Mapped[int] = mapped_column(BigInteger, default=_now)
    expires: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


class Device(Base):
    __tablename__ = "gpodder_devices"
    __table_args__ = (UniqueConstraint("user_id", "deviceid", name="uq_device_user_deviceid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    deviceid: Mapped[str] = mapped_column(String(255))
    caption: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(32), default="other")
    created: Mapped[int] = mapped_column(BigInteger, default=_now)

    user: Mapped[User] = relationship(back_populates="devices")


class Subscription(Base):
    """One row per (user, device, podcast_url) subscription event.

    ``deleted`` stores the timestamp of removal (0 if active). We keep
    historical rows so the ``since=`` delta API can replay changes.
    """

    __tablename__ = "gpodder_subscriptions"
    __table_args__ = (
        Index("ix_sub_user_device", "user_id", "device_id"),
        Index("ix_sub_user_url", "user_id", "podcast_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_devices.id", ondelete="CASCADE")
    )
    podcast_url: Mapped[str] = mapped_column(Text)
    created: Mapped[int] = mapped_column(BigInteger, default=_now, index=True)
    deleted: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


class EpisodeAction(Base):
    __tablename__ = "gpodder_episode_actions"
    __table_args__ = (
        Index("ix_epact_user_ts", "user_id", "uploaded"),
        Index("ix_epact_user_podcast", "user_id", "podcast_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    podcast_url: Mapped[str] = mapped_column(Text)
    episode_url: Mapped[str] = mapped_column(Text)
    guid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp_epoch: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    started: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded: Mapped[int] = mapped_column(BigInteger, default=_now, index=True)


class Setting(Base):
    """Generic key/value setting.

    ``scope`` is one of account/device/podcast/episode. ``target`` carries
    the additional id for non-account scopes (deviceid / podcast url /
    episode url). For ``episode`` scope we also keep ``podcast_url``.
    """

    __tablename__ = "gpodder_settings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope", "target", "podcast_url", "key",
            name="uq_setting_unique",
        ),
        Index("ix_setting_lookup", "user_id", "scope", "target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(16))
    target: Mapped[str] = mapped_column(String(2048), default="")
    podcast_url: Mapped[str] = mapped_column(String(2048), default="")
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)


class PodcastList(Base):
    __tablename__ = "gpodder_lists"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_list_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    podcasts_json: Mapped[str] = mapped_column(Text, default="[]")
    created: Mapped[int] = mapped_column(BigInteger, default=_now)
    updated: Mapped[int] = mapped_column(BigInteger, default=_now)


class Favorite(Base):
    __tablename__ = "gpodder_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_url", name="uq_fav_user_episode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    podcast_url: Mapped[str] = mapped_column(Text)
    episode_url: Mapped[str] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created: Mapped[int] = mapped_column(BigInteger, default=_now)


class SyncGroup(Base):
    """A set of devices syncing together. Membership is exclusive per user."""

    __tablename__ = "gpodder_sync_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SyncGroupMember(Base):
    __tablename__ = "gpodder_sync_group_members"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_syncmember_user_device"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_sync_groups.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_users.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpodder_devices.id", ondelete="CASCADE")
    )
