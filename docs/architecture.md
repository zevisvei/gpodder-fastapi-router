# Architecture

```
src/gpodder_router/
├── __init__.py          GPodderConfig, build_router, attach, lifespan, Database
├── __main__.py          CLI: python -m gpodder_router
├── config.py            pydantic-settings model
├── deps.py              FastAPI deps: SessionDep, ConfigDep, PathUserDep, auth
├── exceptions.py        Typed HTTP errors (401/400/404/409)
├── formats.py           json/xml/opml/txt/jsonp rendering + parsing
├── router.py            build_router(), attach(), lifespan()
├── security.py          bcrypt hash + verify
├── db/                  async SQLAlchemy 2 models + Database class
├── schemas/             Pydantic v2 request / response models
├── services/            Business logic (users, devices, subscriptions, ...)
├── routers/             One sub-router per gpodder API section
└── dashboard/           Admin UI (Jinja2 + PicoCSS)
```

## Request flow

1. ASGI request arrives at FastAPI app.
2. Sub-router matches path (e.g. `/api/2/episodes/{username}.json`).
3. `PathUserDep` runs `authenticate` → checks HTTP Basic OR session
   cookie. On success it verifies the path username matches.
4. `SessionDep` opens a SQLAlchemy `AsyncSession` from the `Database`
   stored on `app.state.gpodder_db`.
5. The route delegates to a `services/*` function that performs the
   actual DB work and returns a Pydantic model.
6. FastAPI serialises the response (JSON by default; alt formats handled
   by `formats.py`).

## Database tables

| Table                          | Purpose                                              |
|--------------------------------|------------------------------------------------------|
| `gpodder_users`                | User accounts (username, bcrypt password hash)       |
| `gpodder_sessions`             | Login session cookies (token, expiry)                |
| `gpodder_devices`              | Devices owned by a user                              |
| `gpodder_subscriptions`        | Subscription rows with `created` / `deleted` ts      |
| `gpodder_episode_actions`      | Episode actions (play / download / delete / ...)    |
| `gpodder_settings`             | Key/value settings, scoped (account/device/...)     |
| `gpodder_lists`                | Podcast lists                                        |
| `gpodder_favorites`            | Favorite episodes per user                           |
| `gpodder_sync_groups`          | Device synchronisation groups                        |
| `gpodder_sync_group_members`   | Membership of sync groups                            |

The `Database` class (`gpodder_router.db.Database`) is a thin wrapper
around `sqlalchemy.ext.asyncio.create_async_engine` plus a session
factory. It supports any URL SQLAlchemy can drive asynchronously; the
project ships extras for SQLite (`aiosqlite`) and PostgreSQL
(`asyncpg`).

## Authentication

Two mechanisms, accepted in this order on every protected endpoint:

1. HTTP Basic — username + bcrypt-verified password.
2. `sessionid` cookie — set on `POST /api/2/auth/{username}/login.json`
   and on `POST /dashboard/login`. Tokens live in
   `gpodder_sessions` with a 30-day default TTL.

This dual path is required by clients such as **AntennaPod** which
perform Basic auth on `login.json` once and rely on the cookie for
subsequent calls.

## Subscription deltas

Subscription rows are append-only:

```
id  user  device  url               created     deleted
1   1     2       https://a/feed    1700000000  0
2   1     2       https://b/feed    1700000010  0
3   1     2       https://b/feed    1700000010  1700000050
```

`POST /api/2/subscriptions/{user}/{device}.json` with `add` / `remove`
arrays writes new rows or sets `deleted = now`. `GET …?since=ts` replays
rows where `created > since` (→ `add`) or `deleted > since` (→ `remove`).
