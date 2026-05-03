# Store API (direct DB access)

Every gpodder endpoint is also exposed as a Python class under
`gpodder_router.services`. Construct a `*Store` with an
`AsyncSession` (and a `User` for user-scoped resources) and call methods
directly. The HTTP routers are thin adapters over these classes — every
API endpoint maps to one or more Store methods.

This is the supported way to script the database from CLI/library code
without going through HTTP and without hand-rolling SQLAlchemy queries.

## Native types

Store methods take and return native Python objects (`datetime`,
enums, dataclasses) rather than the wire-format strings/epoch ints used
by the HTTP layer. The HTTP free functions in each service module remain
available and convert at the boundary.

| Store         | Lives in                         | Ctor                               |
|---------------|----------------------------------|------------------------------------|
| `UserStore`         | `services.users`         | `(session)`                        |
| `SessionStore`      | `services.sessions`      | `(session)`                        |
| `DeviceStore`       | `services.devices`       | `(session, user)`                  |
| `SubscriptionStore` | `services.subscriptions` | `(session, user)`                  |
| `EpisodeStore`      | `services.episodes`      | `(session, user)`                  |
| `SettingStore`      | `services.settings`      | `(session, user)`                  |
| `FavoriteStore`     | `services.favorites`     | `(session, user)`                  |
| `ListStore`         | `services.lists`         | `(session)`                        |
| `SyncStore`         | `services.sync`          | `(session, user)`                  |

## Example

```python
from datetime import datetime, timedelta, UTC

from gpodder_router import Database, GPodderConfig
from gpodder_router.services.users import UserStore
from gpodder_router.services.devices import DeviceStore
from gpodder_router.services.episodes import (
    EpisodeStore,
    EpisodeActionInput,
)
from gpodder_router.schemas.devices import DeviceType, DeviceUpdateData
from gpodder_router.schemas.episodes import EpisodeActionType

config = GPodderConfig(database_url="sqlite+aiosqlite:///gpodder.db")
db = Database(config.database_url)

async with db.session() as session:
    user = await UserStore(session).get("alice")

    # devices: register / rename, list with subscription counts
    devices = DeviceStore(session, user)
    await devices.update(
        "phone-1",
        DeviceUpdateData(caption="Alice's phone", type=DeviceType.mobile),
    )
    for d in await devices.list_with_counts():
        print(d.id, d.caption, d.subscriptions)

    # episode actions tied to that device
    store = EpisodeStore(session, user)
    await store.add_actions([
        EpisodeActionInput(
            podcast="https://example.com/feed.xml",
            episode="https://example.com/ep1.mp3",
            action=EpisodeActionType.play,
            device="phone-1",
            timestamp=datetime.now(UTC),
            position=120,
        ),
    ])

    since = datetime.now(UTC) - timedelta(days=7)
    records, last_dt = await store.list_actions(device="phone-1", since=since)
    for r in records:
        print(r.timestamp, r.action, r.device, r.episode)
```

## Device + sync example

```python
from gpodder_router.services.sync import SyncStore
from gpodder_router.services.subscriptions import SubscriptionStore

async with db.session() as session:
    user = await UserStore(session).get("alice")

    # group two devices to share subscription state
    sync = SyncStore(session, user)
    await sync.update_groups(
        synchronize=[["phone-1", "tablet-1"]],
        stop_synchronize=[],
    )
    grouped, solo = await sync.get_status()

    # subscription deltas for the device's group, since a datetime
    subs = SubscriptionStore(session, user)
    add, remove, ts = await subs.changes_since(
        "phone-1", since=datetime.now(UTC) - timedelta(days=1)
    )
```

## Endpoint → Store method map

### Authentication
| Endpoint                                        | Store call                                          |
|------------------------------------------------|------------------------------------------------------|
| `POST /api/2/auth/{username}/login.json`        | `SessionStore(session).create(user)`                 |
| `POST /api/2/auth/{username}/logout.json`       | `SessionStore(session).revoke(token)`                |
| `POST /api/2/auth/{username}/register.json`     | `UserStore(session).create(...)`                     |

### Devices + sync
| Endpoint                                        | Store call                                           |
|------------------------------------------------|------------------------------------------------------|
| `GET  /api/2/devices/{username}.json`           | `DeviceStore(session, user).list_with_counts()`      |
| `POST /api/2/devices/{username}/{deviceid}.json`| `DeviceStore(session, user).update(deviceid, data)`  |
| `GET  /api/2/updates/{username}/{deviceid}.json`| `SubscriptionStore.changes_since` + `EpisodeStore.list_actions` |
| `GET  /api/2/sync-devices/{username}.json`      | `SyncStore(session, user).get_status()`              |
| `POST /api/2/sync-devices/{username}.json`      | `SyncStore(session, user).update_groups(...)`        |

### Subscriptions
| Endpoint                                                   | Store call                                                          |
|-----------------------------------------------------------|----------------------------------------------------------------------|
| `GET  /subscriptions/{username}/{deviceid}.{format}`       | `SubscriptionStore.current_for_device(device.id)`                    |
| `PUT  /subscriptions/{username}/{deviceid}.{format}`       | `SubscriptionStore.replace_device_subscriptions(deviceid, urls)`     |
| `GET  /subscriptions/{username}.{format}`                  | `SubscriptionStore.current_for_user()`                               |
| `POST /api/2/subscriptions/{username}/{deviceid}.json`     | `SubscriptionStore.apply_changes(deviceid, add, remove)`             |
| `GET  /api/2/subscriptions/{username}/{deviceid}.json`     | `SubscriptionStore.changes_since(deviceid, since_dt)`                |

### Episode actions
| Endpoint                              | Store call                                          |
|--------------------------------------|------------------------------------------------------|
| `POST /api/2/episodes/{username}.json`| `EpisodeStore(session, user).add_actions(inputs)`    |
| `GET  /api/2/episodes/{username}.json`| `EpisodeStore(session, user).list_actions(...)`      |

### Settings, favorites, lists
| Endpoint                                                | Store call                                                         |
|---------------------------------------------------------|---------------------------------------------------------------------|
| `GET/POST /api/2/settings/{username}/{scope}.json`      | `SettingStore.get(scope, ...)` / `SettingStore.save(scope, ...)`    |
| `GET  /api/2/favorites/{username}.json`                 | `FavoriteStore(session, user).list()`                               |
| `GET  /api/2/lists/{username}.json`                     | `ListStore(session).list_for_username(username)`                    |
| `POST /api/2/lists/{username}/create.{format}`          | `ListStore(session).create(user, title=..., podcasts=...)`          |
| `GET  /api/2/lists/{username}/list/{listname}.{format}` | `ListStore(session).get(username, name)`                            |
| `PUT  /api/2/lists/{username}/list/{listname}.{format}` | `ListStore(session).update(user, name, podcasts)`                   |
| `DELETE /api/2/lists/{username}/list/{listname}.{format}`| `ListStore(session).delete(user, name)`                             |

## Backward compatibility

Each service module also exposes the original free functions
(`upload`, `get_actions`, `apply_changes`, ...). They are now thin
wrappers that build a `*Store` and translate epoch ints to `datetime`.
Existing call sites and tests keep working.
