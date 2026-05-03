FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build deps for psycopg/asyncpg if needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast resolver) — optional but mirrors local dev
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY examples ./examples

RUN uv pip install --system --no-cache ".[all]" uvicorn

EXPOSE 8000

ENV GPODDER_DATABASE_URL=sqlite+aiosqlite:////data/gpodder.db \
    GPODDER_BASE_URL=http://localhost:8000

VOLUME ["/data"]

CMD ["uvicorn", "examples.simple_app:app", "--host", "0.0.0.0", "--port", "8000"]
