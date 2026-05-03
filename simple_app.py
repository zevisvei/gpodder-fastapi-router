"""Run a self-contained gpodder.net-compatible server.

    uv run uvicorn examples.simple_app:app --reload

then register a user via POST /api/2/auth/<name>/register.json with JSON
``{"password": "..."}`` (allowed because ``allow_registration`` defaults
to True). Afterwards a normal gpodder client can sync with HTTP Basic auth.
"""
from __future__ import annotations

from fastapi import FastAPI

from src.gpodder_router import GPodderConfig, attach

config = GPodderConfig()

app = FastAPI(title="gpodder.net (self-hosted)")
attach(app, config=config)
