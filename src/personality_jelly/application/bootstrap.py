from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from personality_jelly.core import Settings
from personality_jelly.storage import (
    create_database_engine,
    create_session_factory,
    ensure_database_ready,
)


@dataclass(frozen=True)
class DatabaseResources:
    database_url: str
    engine: Engine
    session_factory: sessionmaker[Session]


def resolve_database_url(
    *,
    settings: Settings,
    database_url: str | None = None,
    memory_db: bool = False,
) -> str:
    if memory_db and database_url:
        raise ValueError("--memory-db cannot be combined with --database-url")
    if memory_db:
        return "sqlite:///:memory:"
    return database_url or settings.database_url


def create_database_resources(
    database_url: str,
    *,
    migrate: bool = True,
) -> DatabaseResources:
    engine = create_database_engine(database_url)
    if migrate:
        ensure_database_ready(engine)
    return DatabaseResources(
        database_url=database_url,
        engine=engine,
        session_factory=create_session_factory(engine),
    )
