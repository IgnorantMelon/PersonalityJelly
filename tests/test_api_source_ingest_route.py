from __future__ import annotations

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import (
    MAX_INLINE_SOURCE_CONTENT_CHARS,
    SOURCE_WORK_INGEST_WORKFLOW_TYPE,
    create_database_resources,
)
from personality_jelly.core import Settings
from personality_jelly.storage import (
    AuditEventRepository,
    IdempotencyRecordRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_post_source_work_creates_safe_write_response_and_diagnostics(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    content = "# Chapter One\n\nLin Shuang observed first.\n\nThen she acted."

    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={
                "X-Request-ID": "req_source_api",
                "Idempotency-Key": "source-create-key",
            },
            json={**_source_body(content=content), "source_work_id": "sw_api"},
        )
        payload = response.json()
        workflow_response = client.get(f"/workflow-runs/{payload['workflow_id']}")
        audit_response = client.get(f"/audit-events/{payload['ids']['audit_event_id']}")

    assert response.status_code == 201
    assert payload["request_id"] == "req_source_api"
    assert payload["workflow_id"].startswith("wf_")
    assert payload["workflow_type"] == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert payload["status"] == "completed"
    assert payload["ids"]["source_work_id"] == "sw_api"
    assert payload["ids"]["audit_event_id"].startswith("audit_")
    assert payload["ids"]["audit_event_ids"] == [payload["ids"]["audit_event_id"]]
    assert payload["ids"]["llm_trace_ids"] == []
    assert payload["warnings"] == []
    assert payload["result"]["source_work"]["id"] == "sw_api"
    assert payload["result"]["source_work"]["title"] == "Inline Source"
    assert payload["result"]["source_work"]["author"] == "Author"
    assert payload["result"]["source_work"]["language"] == "zh-CN"
    assert payload["result"]["source_work"]["source_type"] == "markdown"
    assert payload["result"]["chunk_count"] == 2
    assert payload["result"]["chunk_ids"] == payload["result"]["persisted_ids"][
        "source_chunk_ids"
    ]
    assert payload["result"]["first_chunk_id"] == payload["result"]["chunk_ids"][0]
    assert payload["result"]["last_chunk_id"] == payload["result"]["chunk_ids"][-1]
    assert payload["result"]["text_redacted"] is True
    assert payload["result"]["source_preview_redacted"] is True
    assert "Lin Shuang observed first." not in response.text
    assert "Then she acted." not in response.text
    assert "content" not in payload["result"]

    assert workflow_response.status_code == 200
    workflow = workflow_response.json()
    assert workflow["workflow_type"] == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert workflow["status"] == "completed"
    assert workflow["persisted_ids"]["source_work_id"] == "sw_api"
    assert [link["entity_type"] for link in workflow["links"]].count("source_chunk") == 2
    assert "Lin Shuang observed first." not in workflow_response.text

    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["operation"] == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert audit["entity_type"] == "source_work"
    assert audit["entity_id"] == "sw_api"
    assert audit["after"]["chunk_count"] == 2
    assert audit["after"]["text_redacted"] is True
    assert "Lin Shuang observed first." not in audit_response.text


def test_post_source_work_generates_request_id_when_omitted(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={"Idempotency-Key": "generated-request-key"},
            json=_source_body(source_work_id="sw_generated_request"),
        )

    assert response.status_code == 201
    assert response.json()["request_id"].startswith("req_")


def test_post_source_work_validates_request_id_header_and_body_match(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={
                "X-Request-ID": "req_header",
                "Idempotency-Key": "request-mismatch-key",
            },
            json={**_source_body(), "request_id": "req_body"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "X-Request-ID and body request_id must match"


def test_post_source_work_requires_idempotency_key(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post("/source-works", json=_source_body())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "Idempotency-Key is required"
    _assert_persisted_counts(resources, source_works=0, source_chunks=0, audits=0, workflows=0)


def test_post_source_work_validates_idempotency_key_header_and_body_match(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        matched = client.post(
            "/source-works",
            headers={"Idempotency-Key": "matching-key"},
            json={**_source_body(source_work_id="sw_matching"), "idempotency_key": "matching-key"},
        )
        mismatched = client.post(
            "/source-works",
            headers={"Idempotency-Key": "header-key"},
            json={**_source_body(), "idempotency_key": "body-key"},
        )

    assert matched.status_code == 201
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "validation_error"
    assert (
        mismatched.json()["error"]["message"]
        == "Idempotency-Key and body idempotency_key must match"
    )


def test_post_source_work_replays_without_duplicate_rows(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    body = _source_body(source_work_id="sw_replay")

    with TestClient(app) as client:
        first = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-replay-key"},
            json={**body, "request_id": "req_source_first"},
        )
        second = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-replay-key"},
            json={**body, "request_id": "req_source_second"},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert first.json()["request_id"] == "req_source_first"
    _assert_persisted_counts(
        resources,
        source_works=1,
        source_chunks=2,
        audits=1,
        workflows=1,
        idempotency_records=1,
    )
    with resources.session_factory() as session:
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(
            first.json()["workflow_id"],
        )
        replay = IdempotencyRecordRepository(session).list_all()[0]

    assert len(workflow_links) == 5
    assert replay.response_status_code == 201
    assert replay.replay_payload == first.json()
    assert replay.request_hash != body["content"]
    assert body["content"] not in str(replay.replay_payload)


def test_post_source_work_rejects_idempotency_hash_conflict(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        first = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-conflict-key"},
            json=_source_body(source_work_id="sw_first", content="First paragraph.\n\nSecond."),
        )
        second = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-conflict-key"},
            json=_source_body(source_work_id="sw_second", content="Different paragraph."),
        )

    assert first.status_code == 201
    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["workflow_type"] == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert payload["error"]["details"]["conflict"] == "request_hash_mismatch"
    assert "Different paragraph." not in second.text
    assert "source-conflict-key" not in second.text
    _assert_persisted_counts(resources, source_works=1, workflows=1, idempotency_records=1)


def test_post_source_work_returns_conflict_for_explicit_source_work_id_collision(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        first = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-collision-first"},
            json=_source_body(source_work_id="sw_collision"),
        )
        second = client.post(
            "/source-works",
            headers={"Idempotency-Key": "source-collision-second"},
            json=_source_body(source_work_id="sw_collision", title="Other Title"),
        )

    assert first.status_code == 201
    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["source_work_id"] == "sw_collision"
    _assert_persisted_counts(resources, source_works=1, workflows=1, idempotency_records=1)


def test_post_source_work_rejects_path_fields_and_path_like_metadata_safely(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        extra_field = client.post(
            "/source-works",
            headers={"Idempotency-Key": "path-field-key"},
            json={**_source_body(), "local_path": r"C:\Users\figna\secret.md"},
        )
        metadata_path = client.post(
            "/source-works",
            headers={"Idempotency-Key": "metadata-path-key"},
            json=_source_body(metadata={"label": r"C:\Users\figna\secret.md"}),
        )
        actor_path = client.post(
            "/source-works",
            headers={"Idempotency-Key": "actor-path-key"},
            json=_source_body(actor_metadata={"source_path": r"C:\Users\figna\secret.md"}),
        )

    for response in (extra_field, metadata_path, actor_path):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert r"C:\Users" not in response.text
        assert "secret.md" not in response.text
    _assert_persisted_counts(resources, source_works=0, source_chunks=0, audits=0, workflows=0)


def test_post_source_work_rejects_oversized_content_with_validation_error(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={"Idempotency-Key": "oversized-source-key"},
            json=_source_body(content="x" * (MAX_INLINE_SOURCE_CONTENT_CHARS + 1)),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "at most" in response.json()["error"]["message"]
    _assert_persisted_counts(resources, source_works=0, source_chunks=0, audits=0, workflows=0)


def test_post_source_work_rejects_zero_chunk_content_without_persistence(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={"Idempotency-Key": "zero-chunk-key"},
            json=_source_body(
                content="short",
                chunking={"max_paragraph_chars": 500, "min_paragraph_chars": 20},
            ),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "zero source chunks" in response.json()["error"]["message"]
    _assert_persisted_counts(
        resources,
        source_works=0,
        source_chunks=0,
        audits=0,
        workflows=0,
        idempotency_records=0,
    )


def _resources(tmp_path):
    return create_database_resources(f"sqlite:///{tmp_path / 'api-source-ingest.db'}")


def _source_body(
    *,
    source_work_id: str | None = None,
    title: str = "Inline Source",
    content: str = "First paragraph.\n\nSecond paragraph.",
    metadata: dict | None = None,
    actor_metadata: dict | None = None,
    chunking: dict | None = None,
) -> dict:
    body = {
        "title": title,
        "author": "Author",
        "language": "zh-CN",
        "source_type": "markdown",
        "content": content,
        "content_encoding": "utf-8",
        "chunking": chunking or {"max_paragraph_chars": 500, "min_paragraph_chars": 1},
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "ingest source for route test",
            "metadata": actor_metadata or {"entrypoint": "test"},
        },
        "metadata": metadata or {"client_label": "route-test"},
    }
    if source_work_id is not None:
        body["source_work_id"] = source_work_id
    return body


def _assert_persisted_counts(
    resources,
    *,
    source_works: int | None = None,
    source_chunks: int | None = None,
    audits: int | None = None,
    workflows: int | None = None,
    idempotency_records: int | None = None,
) -> None:
    with resources.session_factory() as session:
        actual = {
            "source_works": len(SourceWorkRepository(session).list_all()),
            "source_chunks": len(SourceChunkRepository(session).list_all()),
            "audits": len(AuditEventRepository(session).list_all()),
            "workflows": len(WorkflowRunRepository(session).list_all()),
            "idempotency_records": len(IdempotencyRecordRepository(session).list_all()),
        }

    expected = {
        "source_works": source_works,
        "source_chunks": source_chunks,
        "audits": audits,
        "workflows": workflows,
        "idempotency_records": idempotency_records,
    }
    for key, value in expected.items():
        if value is not None:
            assert actual[key] == value, key
