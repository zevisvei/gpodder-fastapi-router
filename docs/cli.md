# CLI

The package ships a CLI for offline user/database management. Available
either as a module or — once the package is installed in your env — as
a console script.

```bash
python -m gpodder_router --help
gpodder-router --help
```

Both forms accept a global `--database-url` argument; if omitted, the
value is taken from `GPODDER_DATABASE_URL` or the default
(`sqlite+aiosqlite:///./gpodder.db`).

## Commands

### `init-db`

Create the schema (idempotent — uses `CREATE TABLE IF NOT EXISTS`).

```bash
gpodder-router init-db
gpodder-router --database-url postgresql+asyncpg://gp:pw@db/gpodder init-db
```

### `create-user`

```bash
gpodder-router create-user alice                # prompts for password
gpodder-router create-user alice --password pw  # non-interactive
gpodder-router create-user alice --email a@x.io
```

### `set-password`

```bash
gpodder-router set-password alice
gpodder-router set-password alice --password newpw
```

### `delete-user`

```bash
gpodder-router delete-user bob
```

Cascades through devices, subscriptions, episode actions, settings,
lists, favorites, and sync group memberships.

### `list-users`

```bash
gpodder-router list-users
```

Outputs `id<TAB>username<TAB>email`, one user per line.

## Programmatic equivalent

```python
import asyncio
from gpodder_router import Database, GPodderConfig
from gpodder_router.services import users as users_svc

async def main() -> None:
    cfg = GPodderConfig()
    db = Database(cfg.database_url)
    await db.create_all()
    async with db.session() as s:
        await users_svc.create_user(
            s, username="alice", password="secret",
            bcrypt_rounds=cfg.bcrypt_rounds,
        )
    await db.dispose()

asyncio.run(main())
```
