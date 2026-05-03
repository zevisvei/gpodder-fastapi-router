# Configuration

`GPodderConfig` is a `pydantic-settings` model. Every field can be
overridden via constructor argument or environment variable
(`GPODDER_<FIELD>`).

## Fields

| Field                | Env                          | Default                                     | Description |
|----------------------|------------------------------|---------------------------------------------|-------------|
| `database_url`       | `GPODDER_DATABASE_URL`       | `sqlite+aiosqlite:///./gpodder.db`          | SQLAlchemy async URL |
| `create_tables`      | `GPODDER_CREATE_TABLES`      | `True`                                      | Run `metadata.create_all` on startup |
| `echo_sql`           | `GPODDER_ECHO_SQL`           | `False`                                     | Log SQL statements |
| `allow_registration` | `GPODDER_ALLOW_REGISTRATION` | `True`                                      | Expose `POST /api/2/auth/{u}/register.json` |
| `base_url`           | `GPODDER_BASE_URL`           | `http://localhost:8000`                     | Returned in `/clientconfig.json` |
| `feedservice_url`    | `GPODDER_FEEDSERVICE_URL`    | `http://localhost:8000/feedservice`         | mygpo feedservice URL (informational) |
| `update_timeout`     | `GPODDER_UPDATE_TIMEOUT`     | `604800`                                    | Cache TTL hint for `/clientconfig.json` |
| `bcrypt_rounds`      | `GPODDER_BCRYPT_ROUNDS`      | `12`                                        | Cost factor for password hashing |
| `enable_dashboard`   | `GPODDER_ENABLE_DASHBOARD`   | `True`                                      | Mount `/dashboard` admin UI |
| `dashboard_prefix`   | `GPODDER_DASHBOARD_PREFIX`   | `/dashboard`                                | URL prefix for the dashboard |
| `admin_usernames`    | `GPODDER_ADMIN_USERNAMES`    | `[]`                                        | Whitelist of admin users; empty = first registered user is admin |

## Sources, priority order

`GPodderConfig` resolves values from (highest priority first):

1. Constructor kwargs (`GPodderConfig(database_url=...)`)
2. Environment variables (`GPODDER_*`)
3. `.env` file in CWD
4. Defaults

## Setting via `.env`

Copy [`.env.example`](../.env.example) to `.env`:

```bash
cp .env.example .env
$EDITOR .env
```

The file is read automatically on `GPodderConfig()`.

## Setting via environment

```bash
export GPODDER_DATABASE_URL="postgresql+asyncpg://gp:pw@db:5432/gpodder"
export GPODDER_BASE_URL="https://gpodder.example.com"
export GPODDER_ADMIN_USERNAMES='["alice","bob"]'   # JSON list
uv run uvicorn examples.simple_app:app --host 0.0.0.0 --port 8000
```

`pydantic-settings` parses list fields from a JSON-formatted env var.

## Setting via TOML file

```toml
# config.toml
[gpodder]
database_url = "sqlite+aiosqlite:///./gpodder.db"
base_url = "https://gpodder.example.com"
admin_usernames = ["alice"]
```

```python
from gpodder_router import GPodderConfig
cfg = GPodderConfig.from_toml("config.toml")
# constructor kwargs still win:
cfg = GPodderConfig.from_toml("config.toml", echo_sql=True)
```

See [`examples/config.toml`](../examples/config.toml) and
[`examples/app_from_toml.py`](../examples/app_from_toml.py).

## Setting inline

```python
from gpodder_router import GPodderConfig

cfg = GPodderConfig(
    database_url="postgresql+asyncpg://gp:pw@db/gpodder",
    base_url="https://gpodder.example.com",
    bcrypt_rounds=14,
    admin_usernames=["alice"],
)
```

## Custom config sources

You can subclass to add a `.env` file or other settings sources:

```python
from pydantic_settings import SettingsConfigDict
from gpodder_router import GPodderConfig

class MyConfig(GPodderConfig):
    model_config = SettingsConfigDict(
        env_prefix="GPODDER_", env_file=".env", extra="ignore"
    )
```
