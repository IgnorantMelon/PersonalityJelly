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
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
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
