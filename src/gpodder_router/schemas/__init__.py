from gpodder_router.schemas.common import Format, SettingsScope
from gpodder_router.schemas.devices import (
    DeviceInfo,
    DeviceType,
    DeviceUpdateData,
    DeviceUpdatesResponse,
    SyncStatus,
    SyncStatusRequest,
)
from gpodder_router.schemas.episodes import (
    EpisodeAction,
    EpisodeActionType,
    EpisodeActionsResponse,
    EpisodeActionUploadResponse,
    FavoriteEpisode,
)
from gpodder_router.schemas.lists import PodcastListInfo, PodcastListSummary
from gpodder_router.schemas.parametrization import ClientConfiguration
from gpodder_router.schemas.settings import SaveSettingsRequest, SaveSettingsResponse
from gpodder_router.schemas.subscriptions import (
    SubscriptionChanges,
    SubscriptionChangesResponse,
    SubscriptionUploadResponse,
)
from gpodder_router.schemas.users import RegisterRequest

__all__ = [
    "ClientConfiguration",
    "DeviceInfo",
    "DeviceType",
    "DeviceUpdateData",
    "DeviceUpdatesResponse",
    "EpisodeAction",
    "EpisodeActionType",
    "EpisodeActionUploadResponse",
    "EpisodeActionsResponse",
    "FavoriteEpisode",
    "Format",
    "PodcastListInfo",
    "PodcastListSummary",
    "RegisterRequest",
    "SaveSettingsRequest",
    "SaveSettingsResponse",
    "SettingsScope",
    "SubscriptionChanges",
    "SubscriptionChangesResponse",
    "SubscriptionUploadResponse",
    "SyncStatus",
    "SyncStatusRequest",
]
