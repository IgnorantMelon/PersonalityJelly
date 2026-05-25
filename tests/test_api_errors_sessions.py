from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from personality_jelly.api import create_app
from personality_jelly.api.dependencies import get_session
from personality_jelly.application import DatabaseResources
from personality_jelly.core import Settings
from personality_jelly.storage import create_database_engine, ensure_database_ready


class RecordingSession(Session):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rollback_count = 0
        self.close_count = 0

    def rollback(self) -> None:
        self.rollback_count += 1
        super().rollback()

    def close(self) -> None:
        self.close_count += 1
        super().close()


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def _app(tmp_path, *, recording_sessions: list[RecordingSession] | None = None):
    database_url = f"sqlite:///{tmp_path / 'api-errors-sessions.db'}"
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)

    if recording_sessions is None:
        resources = DatabaseResources(
            database_url=database_url,
            engine=engine,
            session_factory=CallableSessionFactory(lambda: Session(bind=engine)),
        )
    else:
        resources = DatabaseResources(
            database_url=database_url,
            engine=engine,
            session_factory=CallableSessionFactory(
                lambda: _recording_session(engine, recording_sessions)
            ),
        )

    return create_app(settings=_settings(), database_resources=resources)


class CallableSessionFactory:
    def __init__(self, factory: Callable[[], Session]) -> None:
        self._factory = factory

    def __call__(self) -> Session:
        return self._factory()


def _recording_session(engine, sessions: list[RecordingSession]) -> RecordingSession:
    session = RecordingSession(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    sessions.append(session)
    return session


def test_get_session_rolls_back_and_closes_after_successful_request(tmp_path) -> None:
    sessions: list[RecordingSession] = []
    app = _app(tmp_path, recording_sessions=sessions)

    @app.get("/test/session-success")
    def session_success(session: Session = Depends(get_session)) -> dict[str, bool]:
        session.execute(text("SELECT 1"))
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/test/session-success")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(sessions) == 1
    assert sessions[0].rollback_count == 1
    assert sessions[0].close_count == 1


def test_get_session_rolls_back_and_closes_after_exception(tmp_path) -> None:
    sessions: list[RecordingSession] = []
    app = _app(tmp_path, recording_sessions=sessions)

    @app.get("/test/session-error")
    def session_error(session: Session = Depends(get_session)) -> dict[str, bool]:
        session.execute(text("SELECT 1"))
        raise LookupError("missing row")

    with TestClient(app) as client:
        response = client.get("/test/session-error")

    assert response.status_code == 404
    assert len(sessions) == 1
    assert sessions[0].rollback_count == 1
    assert sessions[0].close_count == 1


def test_lookup_errors_use_not_found_envelope(tmp_path) -> None:
    app = _app(tmp_path)

    @app.get("/test/not-found")
    def not_found() -> dict[str, bool]:
        raise LookupError("missing row")

    with TestClient(app) as client:
        response = client.get("/test/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "missing row",
            "details": {},
            "trace_id": None,
        }
    }


def test_value_errors_use_validation_error_envelope(tmp_path) -> None:
    app = _app(tmp_path)

    @app.get("/test/value-error")
    def value_error() -> dict[str, bool]:
        raise ValueError("bad input")

    with TestClient(app) as client:
        response = client.get("/test/value-error")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "bad input",
            "details": {},
            "trace_id": None,
        }
    }


def test_request_validation_errors_keep_field_details_without_stack_trace(tmp_path) -> None:
    app = _app(tmp_path)

    @app.get("/test/request-validation")
    def request_validation(limit: int) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/test/request-validation?limit=not-an-int")

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["trace_id"] is None
    assert body["error"]["details"]["errors"] == [
        {
            "loc": ["query", "limit"],
            "msg": "Input should be a valid integer, unable to parse string as an integer",
            "type": "int_parsing",
        }
    ]


def test_unexpected_errors_use_500_envelope_without_stack_trace(tmp_path) -> None:
    app = _app(tmp_path)

    @app.get("/test/unexpected")
    def unexpected() -> dict[str, bool]:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "unexpected_error",
            "message": "boom",
            "details": {"exception_type": "RuntimeError"},
            "trace_id": None,
        }
    }
