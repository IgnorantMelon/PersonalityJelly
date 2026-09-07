from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from personality_jelly.application import DatabaseResources
from personality_jelly.storage import CURRENT_SCHEMA_VERSION, get_migration_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    database_ready: bool
    schema_version: str | None
    target_schema_version: str
    pending_migrations: int


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    resources: DatabaseResources = request.app.state.database_resources
    migration_status = get_migration_status(resources.engine)
    database_ready = len(migration_status.pending) == 0
    return HealthResponse(
        status="ok" if database_ready else "degraded",
        database_ready=database_ready,
        schema_version=migration_status.current_version,
        target_schema_version=CURRENT_SCHEMA_VERSION,
        pending_migrations=len(migration_status.pending),
    )
