from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
from personality_jelly.storage import CURRENT_SCHEMA_VERSION


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_create_app_registers_health_route_against_injected_database_url(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'api-health.db'}"
    app = create_app(settings=_settings(), database_url=database_url)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database_ready": True,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "target_schema_version": CURRENT_SCHEMA_VERSION,
        "pending_migrations": 0,
    }


def test_create_app_accepts_prebuilt_database_resources(tmp_path) -> None:
    resources = create_database_resources(f"sqlite:///{tmp_path / 'prebuilt.db'}")
    app = create_app(settings=_settings(), database_resources=resources)

    assert app.state.database_resources is resources

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database_ready"] is True


def test_create_app_rejects_ambiguous_database_configuration(tmp_path) -> None:
    resources = create_database_resources(f"sqlite:///{tmp_path / 'prebuilt.db'}")

    with pytest.raises(ValueError, match="database_resources cannot be combined"):
        create_app(
            settings=_settings(),
            database_url="sqlite:///:memory:",
            database_resources=resources,
        )
