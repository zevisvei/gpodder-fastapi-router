"""Run gpodder-fastapi-router with TOML config.

    uv run uvicorn examples.app_from_toml:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from gpodder_router import GPodderConfig, attach

config_path = Path(__file__).with_name("config.toml")
config = GPodderConfig.from_toml(config_path)

app = FastAPI(title="gpodder.net (self-hosted)")
attach(app, config=config)
