from __future__ import annotations

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.api.redaction import REDACTED_REASON
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
from personality_jelly.domain import (
    Character,
    Conversation,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CharacterRepository,
    ContextPackageRepository,
    ConversationRepository,
    IdempotencyRecordRepository,
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_post_conversation_creates_conversation_with_safe_write_response(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_api_create"},
            json={
                "user_id": "user_001",
                "character_id": "char_001",
                "conversation_id": "conv_api",
                "actor": {
                    "actor_id": "api-local:test",
                    "actor_label": "Local API test",
                    "user_id": "user_001",
                    "operation_reason": "Create a local conversation.",
                    "metadata": {"entrypoint": "test"},
                },
            },
        )
        detail_response = client.get("/conversations/conv_api?message_limit=0")

    assert response.status_code == 201
    payload = response.json()
    assert payload["request_id"] == "req_api_create"
    assert payload["workflow_id"].startswith("wf_")
    assert payload["workflow_type"] == "conversation.create"
    assert payload["status"] == "completed"
    assert payload["ids"]["conversation_id"] == "conv_api"
    assert payload["ids"]["user_id"] == "user_001"
    assert payload["ids"]["character_id"] == "char_001"
    assert payload["ids"]["persona_version_id"] == "pv_latest"
    assert payload["result"]["conversation"] == {
        "conversation_id": "conv_api",
        "user_id": "user_001",
        "character_id": "char_001",
        "persona_version_id": "pv_latest",
        "current_mode": "reality_chat",
    }
    audit_event = payload["result"]["audit_event"]
    assert audit_event["operation"] == "conversation.create"
    assert audit_event["persistence"] == "payload_only"
    assert audit_event["reason"] == REDACTED_REASON
    assert audit_event["related_ids"]["conversation_id"] == "conv_api"
    assert audit_event["metadata"]["request_id"] == "req_api_create"
    assert audit_event["metadata"]["workflow_id"] == payload["workflow_id"]

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == "conv_api"
    assert detail["messages"] == []

    with resources.session_factory() as session:
        assert MessageRepository(session).list_all() == []
        assert ContextPackageRepository(session).list_all() == []
        assert LLMRawOutputRepository(session).list_all() == []
        assert IdempotencyRecordRepository(session).list_all() == []


def test_post_conversation_accepts_body_request_id_and_explicit_persona_mode(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            json={
                "request_id": "req_body_create",
                "user_id": "user_001",
                "character_id": "char_001",
                "persona_version_id": "pv_001",
                "interaction_mode": "meta_discussion",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["request_id"] == "req_body_create"
    assert payload["result"]["conversation"]["persona_version_id"] == "pv_001"
    assert payload["result"]["conversation"]["current_mode"] == "meta_discussion"


def test_post_conversation_returns_not_found_envelope_for_missing_required_ids(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_missing_user"},
            json={
                "user_id": "missing_user",
                "character_id": "char_001",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "missing_user",
                },
            },
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert "UserORM 'missing_user' was not found" in payload["error"]["message"]
    assert payload["error"]["details"]["correlation"]["request_id"] == "req_missing_user"
    assert (
        payload["error"]["details"]["correlation"]["failed_step"]
        == "conversation.create"
    )

    with resources.session_factory() as session:
        assert ConversationRepository(session).list_all() == []


def test_post_conversation_returns_validation_error_for_actor_user_mismatch(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_actor_mismatch"},
            json={
                "user_id": "user_001",
                "character_id": "char_001",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_other",
                },
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "local actor context user_id must match user_id"
    assert payload["error"]["details"]["correlation"]["request_id"] == "req_actor_mismatch"


def test_post_conversation_returns_validation_error_for_persona_mismatch(tmp_path) -> None:
    resources = _seeded_resources(tmp_path, include_other_character=True)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_bad_persona"},
            json={
                "user_id": "user_001",
                "character_id": "char_001",
                "persona_version_id": "pv_other",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "does not belong to character" in payload["error"]["message"]


def test_post_conversation_returns_conflict_for_explicit_id_collision(tmp_path) -> None:
    resources = _seeded_resources(tmp_path, include_existing_conversation=True)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_conflict"},
            json={
                "user_id": "user_001",
                "character_id": "char_001",
                "conversation_id": "conv_existing",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["conversation_id"] == "conv_existing"
    assert payload["error"]["details"]["correlation"]["request_id"] == "req_conflict"

    with resources.session_factory() as session:
        assert [conversation.id for conversation in ConversationRepository(session).list_all()] == [
            "conv_existing"
        ]


def test_post_conversation_validates_request_id_header_and_body_match(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        response = client.post(
            "/conversations",
            headers={"X-Request-ID": "req_header"},
            json={
                "request_id": "req_body",
                "user_id": "user_001",
                "character_id": "char_001",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "X-Request-ID and body request_id must match"


def test_post_conversation_replays_idempotency_key_without_duplicate_rows(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    body = {
        "user_id": "user_001",
        "character_id": "char_001",
        "conversation_id": "conv_idempotent",
        "actor": {
            "actor_id": "api-local:test",
            "user_id": "user_001",
        },
    }

    with TestClient(app) as client:
        first = client.post(
            "/conversations",
            headers={"Idempotency-Key": "conversation-retry-key"},
            json={**body, "request_id": "req_create_first"},
        )
        second = client.post(
            "/conversations",
            headers={"Idempotency-Key": "conversation-retry-key"},
            json={**body, "request_id": "req_create_second"},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert first.json()["request_id"] == "req_create_first"

    with resources.session_factory() as session:
        conversations = ConversationRepository(session).list_all()
        workflow_runs = WorkflowRunRepository(session).list_all()
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(
            first.json()["workflow_id"],
        )
        idempotency_records = IdempotencyRecordRepository(session).list_all()

    assert [conversation.id for conversation in conversations] == ["conv_idempotent"]
    assert len(workflow_runs) == 1
    assert workflow_runs[0].request_id == "req_create_first"
    assert len(workflow_links) == 4
    assert len(idempotency_records) == 1
    assert idempotency_records[0].workflow_id == first.json()["workflow_id"]
    assert idempotency_records[0].response_status_code == 201
    assert idempotency_records[0].replay_payload == first.json()


def test_post_conversation_rejects_idempotency_key_hash_conflict(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        first = client.post(
            "/conversations",
            headers={"Idempotency-Key": "conversation-conflict-key"},
            json={
                "request_id": "req_conflict_first",
                "user_id": "user_001",
                "character_id": "char_001",
                "conversation_id": "conv_first",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )
        second = client.post(
            "/conversations",
            headers={"Idempotency-Key": "conversation-conflict-key"},
            json={
                "request_id": "req_conflict_second",
                "user_id": "user_001",
                "character_id": "char_001",
                "conversation_id": "conv_second",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert first.status_code == 201
    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["workflow_type"] == "conversation.create"
    assert payload["error"]["details"]["conflict"] == "request_hash_mismatch"
    assert "conversation-conflict-key" not in second.text

    with resources.session_factory() as session:
        assert [conversation.id for conversation in ConversationRepository(session).list_all()] == [
            "conv_first"
        ]
        assert len(WorkflowRunRepository(session).list_all()) == 1
        assert len(IdempotencyRecordRepository(session).list_all()) == 1


def test_post_conversation_validates_idempotency_key_header_and_body_match(tmp_path) -> None:
    resources = _seeded_resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)

    with TestClient(app) as client:
        matched = client.post(
            "/conversations",
            headers={"Idempotency-Key": "matching-key"},
            json={
                "idempotency_key": "matching-key",
                "user_id": "user_001",
                "character_id": "char_001",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )
        mismatched = client.post(
            "/conversations",
            headers={"Idempotency-Key": "header-key"},
            json={
                "idempotency_key": "body-key",
                "user_id": "user_001",
                "character_id": "char_001",
                "actor": {
                    "actor_id": "api-local:test",
                    "user_id": "user_001",
                },
            },
        )

    assert matched.status_code == 201
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "validation_error"
    assert (
        mismatched.json()["error"]["message"]
        == "Idempotency-Key and body idempotency_key must match"
    )


def _seeded_resources(
    tmp_path,
    *,
    include_existing_conversation: bool = False,
    include_other_character: bool = False,
):
    resources = create_database_resources(
        f"sqlite:///{tmp_path / 'api-conversation-create.db'}"
    )
    with resources.session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Novel", source_type="markdown")
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=1,
                core_self="Careful observer.",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_latest",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=2,
                core_self="Careful observer, latest.",
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="demo-user"))

        if include_existing_conversation:
            ConversationRepository(session).add(
                Conversation(
                    id="conv_existing",
                    user_id="user_001",
                    character_id="char_001",
                    persona_version_id="pv_001",
                )
            )

        if include_other_character:
            SourceWorkRepository(session).add(
                SourceWork(id="sw_002", title="Other Novel", source_type="markdown")
            )
            CharacterRepository(session).add(
                Character(
                    id="char_other",
                    source_work_id="sw_002",
                    canonical_name="Other",
                )
            )
            PersonaVersionRepository(session).add(
                PersonaVersion(
                    id="pv_other",
                    character_id="char_other",
                    source_work_id="sw_002",
                    version_number=1,
                    core_self="Other persona.",
                )
            )

        session.commit()
    return resources
