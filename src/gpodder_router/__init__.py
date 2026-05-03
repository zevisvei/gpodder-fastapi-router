"""FastAPI router implementing the gpodder.net (mygpo) HTTP API.

Mount the router into your FastAPI app to serve the gpodder protocol.

Quick start::

    from fastapi import FastAPI
    from gpodder_router import GPodderConfig, attach

    app = FastAPI()
    attach(app, config=GPodderConfig(database_url="sqlite+aiosqlite:///./gp.db"))
"""

from gpodder_router.config import GPodderConfig
from gpodder_router.db import Database
from gpodder_router.router import attach, build_router, lifespan

__all__ = [
    "Database",
    "GPodderConfig",
    "attach",
    "build_router",
    "lifespan",
]

__version__ = "0.1.0"
