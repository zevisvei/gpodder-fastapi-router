# gpodder-fastapi-router

A pip-installable **FastAPI router** that implements the
[gpodder.net (mygpo) HTTP API](https://gpoddernet.readthedocs.io/en/latest/api/),
ready to drop into any FastAPI application. Bring your own database
(SQLite or PostgreSQL via async SQLAlchemy 2).

Includes:
- All mygpo 2.11 endpoints (auth, directory, devices, sync, subscriptions, episode actions, settings, lists, favorites, suggestions, clientconfig)
- HTTP Basic **and** session-cookie auth (works with AntennaPod, gPodder, Podverse, …)
- Admin **dashboard** at `/dashboard` — users, devices, subscriptions, stats
- **CLI** for offline user management (`gpodder-router create-user …`)
- Auto-generated OpenAPI docs at `/docs` and `/redoc`
- See [`docs/`](docs/index.md) for the full handbook.

## Install

```bash
uv add gpodder-fastapi-router            # core
uv add "gpodder-fastapi-router[sqlite]"  # + aiosqlite driver
uv add "gpodder-fastapi-router[postgresql]"  # + asyncpg driver
```

Requires Python >= 3.12.

## Quick start

```python
from fastapi import FastAPI
from gpodder_router import GPodderConfig, attach

app = FastAPI()
attach(
    app,
    config=GPodderConfig(
        database_url="sqlite+aiosqlite:///./gpodder.db",
        base_url="http://localhost:8000",
    ),
)
```

Run:

```bash
uv run uvicorn examples.simple_app:app --reload
```

Register a user, then point any gpodder-compatible client at the server:

```bash
curl -X POST http://localhost:8000/api/2/auth/alice/register.json \
     -H 'Content-Type: application/json' \
     -d '{"password": "secret"}'
```

## Mounting under a prefix

```python
attach(app, prefix="/gpodder")
# /gpodder/api/2/auth/{username}/login.json ...
```

## Manual integration (no auto startup hooks)

```python
from gpodder_router import Database, GPodderConfig, build_router

cfg = GPodderConfig()
db = Database(cfg.database_url)

app = FastAPI()
app.state.gpodder_config = cfg
app.state.gpodder_db = db
app.include_router(build_router())

@app.on_event("startup")
async def _init() -> None:
    await db.create_all()
```

Or use the bundled lifespan:

```python
from gpodder_router import GPodderConfig, build_router, lifespan

cfg = GPodderConfig()
app = FastAPI(lifespan=lambda a: lifespan(a, config=cfg))
app.include_router(build_router())
```

## Configuration

`GPodderConfig` is a `pydantic-settings` model. Values can be supplied
inline or via `GPODDER_*` environment variables.

| Field                | Env                          | Default                                     |
|----------------------|------------------------------|---------------------------------------------|
| `database_url`       | `GPODDER_DATABASE_URL`       | `sqlite+aiosqlite:///./gpodder.db`          |
| `create_tables`      | `GPODDER_CREATE_TABLES`      | `True`                                      |
| `echo_sql`           | `GPODDER_ECHO_SQL`           | `False`                                     |
| `allow_registration` | `GPODDER_ALLOW_REGISTRATION` | `True` (extension endpoint)                 |
| `base_url`           | `GPODDER_BASE_URL`           | `http://localhost:8000`                     |
| `feedservice_url`    | `GPODDER_FEEDSERVICE_URL`    | `http://localhost:8000/feedservice`         |
| `update_timeout`     | `GPODDER_UPDATE_TIMEOUT`     | `604800` (1 week)                           |
| `bcrypt_rounds`      | `GPODDER_BCRYPT_ROUNDS`      | `12`                                        |

PostgreSQL example:

```python
GPodderConfig(
    database_url="postgresql+asyncpg://gpodder:pw@localhost:5432/gpodder",
)
```

## Implemented endpoints

All endpoints from
[mygpo OpenAPI 2.11](https://github.com/gpodder/mygpo/blob/master/mygpo/api/openapi.yaml):

| Section                  | Endpoints                                                                                                                            |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| Client Parametrization   | `GET /clientconfig.json`                                                                                                             |
| Authentication           | `POST /api/2/auth/{username}/login.json`, `.../logout.json`, `.../register.json`*                                                    |
| Directory                | `GET /api/2/tags/{count}.json`, `/api/2/tag/{tag}/{count}.json`, `/api/2/data/podcast.json`, `/api/2/data/episode.json`, `/toplist`, `/search` |
| Suggestions              | `GET /suggestions/{number}.{format}`                                                                                                 |
| Devices                  | `GET /api/2/devices/{username}.json`, `POST /api/2/devices/{username}/{deviceid}.json`, `GET /api/2/updates/{username}/{deviceid}.json` |
| Device Sync              | `GET`/`POST /api/2/sync-devices/{username}.json`                                                                                     |
| Subscriptions (simple)   | `GET`/`PUT /subscriptions/{username}/{deviceid}.{format}`, `GET /subscriptions/{username}.{format}`                                   |
| Subscriptions (advanced) | `POST`/`GET /api/2/subscriptions/{username}/{deviceid}.json`                                                                         |
| Episode Actions          | `POST`/`GET /api/2/episodes/{username}.json`                                                                                         |
| Settings                 | `GET`/`POST /api/2/settings/{username}/{scope}.json`                                                                                 |
| Favorites                | `GET /api/2/favorites/{username}.json`                                                                                               |
| Podcast Lists            | `GET /api/2/lists/{username}.json`, `POST /api/2/lists/{username}/create.{format}`, `GET`/`PUT`/`DELETE /api/2/lists/{username}/list/{listname}.{format}` |

\* `register.json` is an extension on top of mygpo. Disable via
`GPodderConfig(allow_registration=False)` to require server-side
provisioning.

Supported response formats: `json`, `xml`, `opml`, `txt`, `jsonp`.

Directory / suggestions / favorites are stub-implemented (returning
empty result sets) since a self-hosted server has no global directory.
The schema is in place; populate the `gpodder_favorites` table or
override the routers to plug in your own data sources.

## Programmatic user management

```python
from gpodder_router import Database, GPodderConfig
from gpodder_router.services import users as users_svc

cfg = GPodderConfig()
db = Database(cfg.database_url)
await db.create_all()
async with db.session() as s:
    await users_svc.create_user(s, username="alice", password="secret")
```

## Authentication

HTTP Basic, exactly as mygpo. Passwords are stored as bcrypt hashes.
Path-`{username}` is verified against the authenticated user; a
mismatch returns `400`, matching the upstream contract.

## Dashboard

Mounted at `/dashboard` (toggle with `enable_dashboard`, change with
`dashboard_prefix`). The first registered user is the bootstrap admin;
in production set `admin_usernames=["alice", ...]`. See
[docs/dashboard.md](docs/dashboard.md).

## CLI

```bash
gpodder-router create-user alice           # prompts for password
gpodder-router list-users
gpodder-router set-password alice
gpodder-router delete-user bob
gpodder-router init-db
```

Same operations also available as `python -m gpodder_router …`. See
[docs/cli.md](docs/cli.md).

## Configuration files

Three ways to configure (priority highest → lowest):

1. **kwargs** — `GPodderConfig(database_url=..., base_url=...)`
2. **env** — `GPODDER_*` variables, optionally loaded from a [`.env`](.env.example) file
3. **TOML** — `GPodderConfig.from_toml("config.toml")` — see [`examples/config.toml`](examples/config.toml)

```bash
cp .env.example .env   # then edit
```

## Docker

```bash
docker compose up -d                                 # SQLite
docker compose -f docker-compose.postgres.yml up -d  # PostgreSQL
```

## Documentation

- [docs/index.md](docs/index.md) — overview
- [docs/architecture.md](docs/architecture.md) — package layout, request flow, schema
- [docs/configuration.md](docs/configuration.md) — every config field
- [docs/deployment.md](docs/deployment.md) — uvicorn, proxies, ngrok, Postgres, Docker
- [docs/dashboard.md](docs/dashboard.md) — admin UI
- [docs/cli.md](docs/cli.md) — command-line tool
- [docs/api-reference.md](docs/api-reference.md) — endpoint table
- [docs/clients.md](docs/clients.md) — AntennaPod / gPodder / Podverse compatibility

Live API docs once running:

- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/redoc` (ReDoc)
- `http://localhost:8000/openapi.json`

## Development

```bash
uv sync --extra sqlite --group dev
uv run pytest
uv run uvicorn examples.simple_app:app --reload
```

## License

GPL-3.0-or-later.
