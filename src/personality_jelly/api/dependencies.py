from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from personality_jelly.application import DatabaseResources
from personality_jelly.core import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database_resources(request: Request) -> DatabaseResources:
    return request.app.state.database_resources


def get_session(request: Request) -> Iterator[Session]:
    resources = get_database_resources(request)
    session = resources.session_factory()
    try:
        yield session
        session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
