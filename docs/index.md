# gpodder-fastapi-router

Pip-installable FastAPI router that implements the
[gpodder.net (mygpo) HTTP API](https://gpoddernet.readthedocs.io/en/latest/api/),
plus an admin dashboard and a CLI.

## Documentation

- [Architecture](architecture.md) — package layout, request flow, DB schema
- [Configuration](configuration.md) — `GPodderConfig` fields and env vars
- [Deployment](deployment.md) — uvicorn, behind reverse proxy, ngrok, Postgres
- [Dashboard](dashboard.md) — admin UI: users, devices, stats
- [CLI](cli.md) — `python -m gpodder_router` / `gpodder-router`
- [API reference](api-reference.md) — endpoint overview + auto-generated docs
- [Store API](store-api.md) — direct DB access classes (no HTTP) used by the API
- [Client compatibility](clients.md) — AntennaPod, gPodder, Podverse...

## Live API documentation

Once the server is running, visit:

- `http://localhost:8000/docs` — Swagger UI (interactive)
- `http://localhost:8000/redoc` — ReDoc (read-only)
- `http://localhost:8000/openapi.json` — raw OpenAPI 3 schema

These are produced automatically by FastAPI from the Pydantic models; the
admin dashboard links to them.
