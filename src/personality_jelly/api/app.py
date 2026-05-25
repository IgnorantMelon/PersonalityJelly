from __future__ import annotations

from fastapi import FastAPI

from personality_jelly.api.errors import register_exception_handlers
from personality_jelly.api.routes import conversations, health
from personality_jelly.application import (
    DatabaseResources,
    create_database_resources,
    resolve_database_url,
)
from personality_jelly.core import Settings


def create_app(
    *,
    settings: Settings | None = None,
    database_url: str | None = None,
    database_resources: DatabaseResources | None = None,
    migrate: bool = True,
) -> FastAPI:
    """Create the read-only HTTP adapter app without starting a server."""
    if database_resources is not None and database_url is not None:
        raise ValueError("database_resources cannot be combined with database_url")

    resolved_settings = settings or Settings()
    resources = database_resources
    if resources is None:
        resolved_database_url = resolve_database_url(
            settings=resolved_settings,
            database_url=database_url,
        )
        resources = create_database_resources(resolved_database_url, migrate=migrate)

    app = FastAPI(title="Personality Jelly API")
    app.state.settings = resolved_settings
    app.state.database_resources = resources
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(conversations.router)
    return app
