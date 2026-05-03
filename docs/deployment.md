# Deployment

## Local development

```bash
uv sync --extra sqlite --group dev
uv run uvicorn examples.simple_app:app --reload --port 8000
```

## Production: uvicorn

```bash
uv pip install "gpodder-fastapi-router[postgresql]" uvicorn
GPODDER_DATABASE_URL="postgresql+asyncpg://gp:pw@db:5432/gpodder" \
GPODDER_BASE_URL="https://gpodder.example.com" \
GPODDER_ADMIN_USERNAMES='["alice"]' \
  uvicorn myapp:app --host 0.0.0.0 --port 8000 --workers 4
```

Where `myapp.py` is:

```python
from fastapi import FastAPI
from gpodder_router import attach

app = FastAPI()
attach(app)
```

## Behind a reverse proxy

When proxied (nginx, Caddy, Traefik), set `--proxy-headers` and
`--forwarded-allow-ips` so uvicorn trusts `X-Forwarded-*`:

```bash
uvicorn myapp:app --proxy-headers --forwarded-allow-ips="*"
```

Also set `GPODDER_BASE_URL` to the public URL so `/clientconfig.json`
returns sensible values.

## ngrok

```bash
ngrok http 8000
```

ngrok's free tier rotates the host on every restart. AntennaPod and
gpodder use the host you typed into the app, not `clientconfig.json`,
so it works unchanged. If you serve other clients that *do* read
`clientconfig.json`, set `base_url` to the current ngrok URL.

## PostgreSQL

```sql
CREATE DATABASE gpodder;
CREATE USER gp WITH PASSWORD 'pw';
GRANT ALL PRIVILEGES ON DATABASE gpodder TO gp;
```

```bash
uv add "gpodder-fastapi-router[postgresql]"
export GPODDER_DATABASE_URL="postgresql+asyncpg://gp:pw@localhost:5432/gpodder"
```

`create_tables=True` (the default) runs `CREATE TABLE IF NOT EXISTS` on
startup. For schema migrations between versions, manage with Alembic:

```bash
uv add alembic
alembic init alembic
# point env.py target_metadata = gpodder_router.db.Base.metadata
```

## Docker

The repo ships a [`Dockerfile`](../Dockerfile) and two compose files:

### SQLite (single container)

```bash
docker compose up -d
```

Uses [`docker-compose.yml`](../docker-compose.yml). Data persists in
the named volume `gpodder-data`. Override env vars via `.env` next to
the compose file or with `-e` flags.

### PostgreSQL (api + db)

```bash
POSTGRES_PASSWORD=changeme \
GPODDER_BASE_URL=https://gpodder.example.com \
GPODDER_ADMIN_USERNAMES='["alice"]' \
  docker compose -f docker-compose.postgres.yml up -d
```

Uses [`docker-compose.postgres.yml`](../docker-compose.postgres.yml).

### Custom image

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir "gpodder-fastapi-router[postgresql]" uvicorn
COPY myapp.py /app/myapp.py
WORKDIR /app
ENV GPODDER_DATABASE_URL=postgresql+asyncpg://gp:pw@db:5432/gpodder
EXPOSE 8000
CMD ["uvicorn", "myapp:app", "--host", "0.0.0.0", "--port", "8000"]
```
