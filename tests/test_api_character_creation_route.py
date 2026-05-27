from __future__ import annotations

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import (
    CHARACTER_CREATE_WORKFLOW_TYPE,
    SOURCE_WORK_INGEST_WORKFLOW_TYPE,
    create_database_resources,
)
from personality_jelly.core import Settings
from personality_jelly.storage import (
    AuditEventRepository,
    CharacterRepository,
    IdempotencyRecordRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_post_character_after_source_work_creates_safe_response_and_diagnostics(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    source_content = "# Chapter One\n\nLin Shuang observed first.\n\nThen she acted."

    with TestClient(app) as client:
        source = _post_source(
            client,
            source_work_id="sw_character_api",
            content=source_content,
        )
        response = client.post(
            "/characters",
            headers={"X-Request-ID": "req_character_api"},
            json=_character_body(
                source_work_id=source.json()["ids"]["source_work_id"],
                character_id="char_api",
                canonical_name="  Lin   Shuang ",
                aliases=["A Shuang", "Lin Shuang", "", "A Shuang"],
            ),
        )
        payload = response.json()
        workflow_response = client.get(f"/workflow-runs/{payload['workflow_id']}")
        audit_response = client.get(f"/audit-events/{payload['ids']['audit_event_id']}")
        workflow_list = client.get(
            "/workflow-runs",
            params={"workflow_type": CHARACTER_CREATE_WORKFLOW_TYPE},
        )

    assert source.status_code == 201
    assert response.status_code == 201
    assert payload["request_id"] == "req_character_api"
    assert payload["workflow_id"].startswith("wf_")
    assert payload["workflow_type"] == CHARACTER_CREATE_WORKFLOW_TYPE
    assert payload["status"] == "completed"
    assert payload["ids"]["source_work_id"] == "sw_character_api"
    assert payload["ids"]["character_id"] == "char_api"
    assert payload["ids"]["audit_event_id"].startswith("audit_")
    assert payload["ids"]["audit_event_ids"] == [payload["ids"]["audit_event_id"]]
    assert payload["ids"]["llm_trace_ids"] == []
    assert payload["warnings"] == []
    assert payload["result"]["character"] == {
        "character_id": "char_api",
        "source_work_id": "sw_character_api",
        "canonical_name": "Lin Shuang",
        "aliases": ["A Shuang"],
        "latest_persona_version_id": None,
    }
    assert payload["result"]["audit_event"]["operation"] == CHARACTER_CREATE_WORKFLOW_TYPE
    assert payload["result"]["audit_event"]["reason"] == "[redacted:reason]"
    assert "Lin Shuang observed first." not in response.text
    assert "Then she acted." not in response.text
    assert "provider_config" not in response.text
    assert "prompt" not in response.text

    assert workflow_response.status_code == 200
    workflow = workflow_response.json()
    assert workflow["workflow_type"] == CHARACTER_CREATE_WORKFLOW_TYPE
    assert workflow["persisted_ids"]["source_work_id"] == "sw_character_api"
    assert workflow["persisted_ids"]["character_id"] == "char_api"
    assert {(link["entity_type"], link["entity_id"], link["relation"]) for link in workflow["links"]} == {
        ("source_work", "sw_character_api", "input"),
        ("character", "char_api", "created"),
        ("audit_event", payload["ids"]["audit_event_id"], "audit"),
    }
    assert "Lin Shuang observed first." not in workflow_response.text

    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["operation"] == CHARACTER_CREATE_WORKFLOW_TYPE
    assert audit["entity_type"] == "character"
    assert audit["entity_id"] == "char_api"
    assert audit["related_ids"] == {
        "source_work_id": "sw_character_api",
        "character_id": "char_api",
    }
    assert audit["after"]["latest_persona_version_id"] is None
    assert audit["metadata"]["alias_count"] == 1
    assert audit["metadata"]["source_text_redacted"] is True
    assert "Lin Shuang observed first." not in audit_response.text

    assert workflow_list.status_code == 200
    assert [item["workflow_id"] for item in workflow_list.json()["items"]] == [
        payload["workflow_id"]
    ]


def test_post_character_generates_request_id_when_omitted(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_generated")
        response = client.post(
            "/characters",
            json=_character_body(source_work_id="sw_generated", character_id="char_generated"),
        )

    assert response.status_code == 201
    assert response.json()["request_id"].startswith("req_")


def test_post_character_validates_request_id_header_and_body_match(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_request_mismatch")
        response = client.post(
            "/characters",
            headers={"X-Request-ID": "req_header"},
            json={
                **_character_body(source_work_id="sw_request_mismatch"),
                "request_id": "req_body",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "X-Request-ID and body request_id must match"
    _assert_character_counts(resources, characters=0, character_workflows=0)


def test_post_character_replays_optional_idempotency_without_duplicate_rows(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    body = _character_body(source_work_id="sw_replay", character_id="char_replay")

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_replay")
        first = client.post(
            "/characters",
            headers={"Idempotency-Key": "character-replay-key"},
            json={**body, "request_id": "req_character_first"},
        )
        second = client.post(
            "/characters",
            headers={"Idempotency-Key": "character-replay-key"},
            json={**body, "request_id": "req_character_second"},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert first.json()["request_id"] == "req_character_first"
    _assert_character_counts(
        resources,
        characters=1,
        audits=1,
        character_workflows=1,
        idempotency_records=2,
    )
    with resources.session_factory() as session:
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(
            first.json()["workflow_id"],
        )
        replay = [
            record
            for record in IdempotencyRecordRepository(session).list_all()
            if record.workflow_type == CHARACTER_CREATE_WORKFLOW_TYPE
        ][0]

    assert len(workflow_links) == 4
    assert replay.response_status_code == 201
    assert replay.replay_payload == first.json()
    assert body["canonical_name"] not in replay.request_hash


def test_post_character_rejects_idempotency_hash_conflict(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_idempotency_conflict")
        first = client.post(
            "/characters",
            headers={"Idempotency-Key": "character-conflict-key"},
            json=_character_body(
                source_work_id="sw_idempotency_conflict",
                character_id="char_first",
                canonical_name="Lin Shuang",
            ),
        )
        second = client.post(
            "/characters",
            headers={"Idempotency-Key": "character-conflict-key"},
            json=_character_body(
                source_work_id="sw_idempotency_conflict",
                character_id="char_second",
                canonical_name="Other Name",
            ),
        )

    assert first.status_code == 201
    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["workflow_type"] == CHARACTER_CREATE_WORKFLOW_TYPE
    assert payload["error"]["details"]["conflict"] == "request_hash_mismatch"
    assert "Other Name" not in second.text
    assert "character-conflict-key" not in second.text
    _assert_character_counts(resources, characters=1, character_workflows=1)


def test_post_character_returns_conflict_for_duplicate_name_and_explicit_id_collision(
    tmp_path,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_conflict")
        first = client.post(
            "/characters",
            json=_character_body(source_work_id="sw_conflict", character_id="char_existing"),
        )
        duplicate_name = client.post(
            "/characters",
            json=_character_body(
                source_work_id="sw_conflict",
                character_id="char_duplicate",
                canonical_name="  Lin   Shuang ",
            ),
        )
        id_collision = client.post(
            "/characters",
            json=_character_body(
                source_work_id="sw_conflict",
                character_id="char_existing",
                canonical_name="Other Name",
            ),
        )

    assert first.status_code == 201
    for response in (duplicate_name, id_collision):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"
    _assert_character_counts(resources, characters=1, audits=1, character_workflows=1)


def test_post_character_returns_not_found_for_missing_source_work(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/characters",
            json=_character_body(source_work_id="missing_source"),
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    _assert_character_counts(resources, characters=0, audits=0, character_workflows=0)


def test_post_character_rejects_path_metadata_provider_prompt_source_and_secret_fields(
    tmp_path,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_reject")
        responses = [
            client.post(
                "/characters",
                json=_character_body(
                    source_work_id="sw_reject",
                    metadata={"label": r"C:\Users\figna\secret.md"},
                ),
            ),
            client.post(
                "/characters",
                json=_character_body(
                    source_work_id="sw_reject",
                    metadata={"provider_config": {"model": "x"}},
                ),
            ),
            client.post(
                "/characters",
                json=_character_body(
                    source_work_id="sw_reject",
                    metadata={"raw_prompt": "extract character"},
                ),
            ),
            client.post(
                "/characters",
                json=_character_body(
                    source_work_id="sw_reject",
                    metadata={"source_text": "raw source"},
                ),
            ),
            client.post(
                "/characters",
                json=_character_body(
                    source_work_id="sw_reject",
                    metadata={"api_key": "sk-secret-value"},
                ),
            ),
        ]

    for response in responses:
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert r"C:\Users" not in response.text
        assert "secret.md" not in response.text
        assert "sk-secret-value" not in response.text
        assert "extract character" not in response.text
        assert "raw source" not in response.text
    _assert_character_counts(resources, characters=0, audits=0, character_workflows=0)


def test_post_character_validates_idempotency_header_and_body_match(tmp_path) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_idempotency_mismatch")
        matched = client.post(
            "/characters",
            headers={"Idempotency-Key": "matching-key"},
            json={
                **_character_body(
                    source_work_id="sw_idempotency_mismatch",
                    character_id="char_matching",
                ),
                "idempotency_key": "matching-key",
            },
        )
        mismatched = client.post(
            "/characters",
            headers={"Idempotency-Key": "header-key"},
            json={
                **_character_body(source_work_id="sw_idempotency_mismatch"),
                "idempotency_key": "body-key",
            },
        )

    assert matched.status_code == 201
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "validation_error"
    assert (
        mismatched.json()["error"]["message"]
        == "Idempotency-Key and body idempotency_key must match"
    )


def _resources(tmp_path):
    return create_database_resources(f"sqlite:///{tmp_path / 'api-character-create.db'}")


def _post_source(
    client: TestClient,
    *,
    source_work_id: str,
    content: str = "First paragraph.\n\nSecond paragraph.",
):
    return client.post(
        "/source-works",
        headers={"Idempotency-Key": f"source-key-{source_work_id}"},
        json=_source_body(source_work_id=source_work_id, content=content),
    )


def _source_body(*, source_work_id: str, content: str) -> dict:
    return {
        "source_work_id": source_work_id,
        "title": "Inline Source",
        "author": "Author",
        "language": "zh-CN",
        "source_type": "markdown",
        "content": content,
        "content_encoding": "utf-8",
        "chunking": {"max_paragraph_chars": 500, "min_paragraph_chars": 1},
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "ingest source for character route test",
            "metadata": {"entrypoint": "test"},
        },
        "metadata": {"client_label": "character-route-test"},
    }


def _character_body(
    *,
    source_work_id: str,
    character_id: str = "char_api",
    canonical_name: str = "Lin Shuang",
    aliases: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "source_work_id": source_work_id,
        "character_id": character_id,
        "canonical_name": canonical_name,
        "aliases": aliases if aliases is not None else ["A Shuang"],
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "create character for route test",
            "metadata": {"entrypoint": "test"},
        },
        "metadata": metadata or {"client_label": "route-test"},
    }


def _assert_character_counts(
    resources,
    *,
    characters: int,
    audits: int | None = None,
    character_workflows: int | None = None,
    idempotency_records: int | None = None,
) -> None:
    with resources.session_factory() as session:
        workflows = WorkflowRunRepository(session).list_all()
        actual = {
            "source_works": len(SourceWorkRepository(session).list_all()),
            "source_chunks": len(SourceChunkRepository(session).list_all()),
            "characters": len(CharacterRepository(session).list_all()),
            "audits": len(
                [
                    event
                    for event in AuditEventRepository(session).list_all()
                    if event.operation == CHARACTER_CREATE_WORKFLOW_TYPE
                ]
            ),
            "character_workflows": len(
                [
                    workflow
                    for workflow in workflows
                    if workflow.workflow_type == CHARACTER_CREATE_WORKFLOW_TYPE
                ]
            ),
            "idempotency_records": len(IdempotencyRecordRepository(session).list_all()),
        }

    assert actual["source_works"] >= 0
    assert actual["source_chunks"] >= 0
    assert characters == actual["characters"]
    if audits is not None:
        assert audits == actual["audits"]
    if character_workflows is not None:
        assert character_workflows == actual["character_workflows"]
    if idempotency_records is not None:
        assert idempotency_records == actual["idempotency_records"]
