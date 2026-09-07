from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.api.redaction import REDACTED_REASON, REDACTED_SECRET, REDACTED_USER_TEXT
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
from personality_jelly.domain import (
    Character,
    Conversation,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CharacterRepository,
    ConversationRepository,
    IdempotencyRecordRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    WorkflowRunRepository,
)
from personality_jelly.storage.database import session_scope


NOW = datetime(2026, 5, 26, 10, 0, tzinfo=timezone.utc)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_review_memory_route_updates_candidate_and_returns_redacted_audit(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/memories/mem_candidate/review",
            headers={"X-Request-ID": "req_review_route"},
            json={
                "actor": _actor_body(),
                "decision": "accept",
                "reason": "User confirmed this relationship note.",
                "user_id": "user_001",
                "character_id": "char_001",
                "conversation_id": "conv_001",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req_review_route"
    assert body["workflow_id"].startswith("wf_")
    assert body["workflow_type"] == "memory.review"
    assert body["status"] == "completed"
    assert body["ids"]["memory_id"] == "mem_candidate"
    assert body["ids"]["user_id"] == "user_001"
    assert body["ids"]["audit_event_id"].startswith("audit_")
    assert body["result"]["memory"]["status"] == "accepted"
    assert body["result"]["memory"]["content"] == REDACTED_USER_TEXT
    assert body["result"]["memory"]["reason"] == REDACTED_REASON
    audit = body["result"]["audit_event"]
    assert audit["persistence"] == "payload_only"
    assert audit["operation"] == "memory.review"
    assert audit["reason"] == REDACTED_REASON
    assert audit["before"]["content"] == REDACTED_USER_TEXT
    assert audit["before"]["reason"] == REDACTED_REASON
    assert audit["after"]["content"] == REDACTED_USER_TEXT
    assert audit["after"]["reason"] == REDACTED_REASON
    assert audit["metadata"]["request_id"] == "req_review_route"
    assert audit["metadata"]["workflow_id"] == body["workflow_id"]
    assert audit["metadata"]["workflow_status"] == "completed"
    assert audit["metadata"]["result"] == "succeeded"
    assert "User confirmed this relationship note." not in response.text
    assert "Lin Shuang and the user are building trust." not in response.text

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_candidate")

    assert memory.status == "accepted"
    assert "Review decision accepted: User confirmed this relationship note." in memory.reason


def test_review_memory_route_replays_idempotency_key_without_duplicate_rows(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)
    body = {
        "actor": _actor_body(),
        "decision": "accept",
        "reason": "User confirmed this relationship note.",
        "user_id": "user_001",
        "character_id": "char_001",
        "conversation_id": "conv_001",
    }

    with TestClient(app) as client:
        first = client.post(
            "/memories/mem_candidate/review",
            headers={"Idempotency-Key": "memory-review-key"},
            json={**body, "request_id": "req_review_first"},
        )
        second = client.post(
            "/memories/mem_candidate/review",
            headers={"Idempotency-Key": "memory-review-key"},
            json={**body, "request_id": "req_review_second"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert first.json()["request_id"] == "req_review_first"

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_candidate")
        workflow_runs = WorkflowRunRepository(session).list_all()
        idempotency_records = IdempotencyRecordRepository(session).list_all()

    assert memory.status == "accepted"
    assert len(workflow_runs) == 1
    assert len(idempotency_records) == 1
    record = idempotency_records[0]
    assert record.workflow_type == "memory.review"
    assert record.replay_payload == first.json()
    assert REDACTED_USER_TEXT in repr(record.replay_payload)
    assert "Lin Shuang and the user are building trust." not in repr(record.replay_payload)


def test_edit_memory_route_commits_update_and_sanitizes_payload_metadata(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.patch(
            "/memories/mem_accepted",
            json={
                "request_id": "req_edit_route",
                "actor": _actor_body(metadata={"api_key": "sk-actor-secret"}),
                "content": "User prefers drafting after midnight.",
                "reason": "Manual correction after user clarification.",
                "metadata": {"client_note": "memory review panel"},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req_edit_route"
    assert body["workflow_type"] == "memory.edit"
    assert body["result"]["memory"]["content"] == REDACTED_USER_TEXT
    assert body["result"]["memory"]["reason"] == REDACTED_REASON
    audit = body["result"]["audit_event"]
    assert audit["metadata"]["client_note"] == "memory review panel"
    assert audit["metadata"]["actor_metadata"]["api_key"] == REDACTED_SECRET
    assert "sk-actor-secret" not in response.text
    assert "User prefers drafting after midnight." not in response.text

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_accepted")

    assert memory.content == "User prefers drafting after midnight."
    assert memory.reason == "Manual correction after user clarification."


def test_edit_memory_route_replays_and_rejects_hash_conflict(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)
    body = {
        "actor": _actor_body(),
        "content": "User prefers drafting after midnight.",
        "reason": "Manual correction after user clarification.",
    }

    with TestClient(app) as client:
        first = client.patch(
            "/memories/mem_accepted",
            headers={"Idempotency-Key": "memory-edit-key"},
            json={**body, "request_id": "req_edit_first"},
        )
        replay = client.patch(
            "/memories/mem_accepted",
            headers={"Idempotency-Key": "memory-edit-key"},
            json={**body, "request_id": "req_edit_second"},
        )
        conflict = client.patch(
            "/memories/mem_accepted",
            headers={"Idempotency-Key": "memory-edit-key"},
            json={
                **body,
                "request_id": "req_edit_conflict",
                "content": "User prefers sunrise drafting.",
            },
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"
    assert conflict.json()["error"]["details"]["workflow_type"] == "memory.edit"
    assert conflict.json()["error"]["details"]["conflict"] == "request_hash_mismatch"
    assert "User prefers sunrise drafting." not in conflict.text

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_accepted")
        workflow_runs = WorkflowRunRepository(session).list_all()
        idempotency_records = IdempotencyRecordRepository(session).list_all()

    assert memory.content == "User prefers drafting after midnight."
    assert len(workflow_runs) == 1
    assert len(idempotency_records) == 1


def test_archive_memory_route_changes_status_with_payload_only_audit(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/memories/mem_accepted/archive",
            json={
                "request_id": "req_archive_route",
                "actor": _actor_body(),
                "reason": "User asked to remove stale memory.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_type"] == "memory.archive"
    assert body["result"]["memory"]["status"] == "archived"
    assert body["result"]["audit_event"]["persistence"] == "payload_only"
    assert body["result"]["audit_event"]["after"]["status"] == "archived"
    assert body["result"]["audit_event"]["reason"] == REDACTED_REASON

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_accepted")

    assert memory.status == "archived"


def test_archive_memory_route_replays_idempotency_key_without_duplicate_rows(tmp_path) -> None:
    app, resources = _seed_api_app(tmp_path)
    body = {
        "actor": _actor_body(),
        "reason": "User asked to remove stale memory.",
    }

    with TestClient(app) as client:
        first = client.post(
            "/memories/mem_accepted/archive",
            headers={"Idempotency-Key": "memory-archive-key"},
            json={**body, "request_id": "req_archive_first"},
        )
        second = client.post(
            "/memories/mem_accepted/archive",
            headers={"Idempotency-Key": "memory-archive-key"},
            json={**body, "request_id": "req_archive_second"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    with session_scope(resources.session_factory) as session:
        memory = MemoryRepository(session).require("mem_accepted")
        workflow_runs = WorkflowRunRepository(session).list_all()
        idempotency_records = IdempotencyRecordRepository(session).list_all()

    assert memory.status == "archived"
    assert len(workflow_runs) == 1
    assert len(idempotency_records) == 1


def test_memory_mutation_routes_use_error_envelope_for_missing_actor_reason_and_ids(
    tmp_path,
) -> None:
    app, _resources = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        missing_actor = client.post(
            "/memories/mem_candidate/review",
            json={
                "decision": "accept",
                "reason": "Review reason.",
            },
        )
        missing_reason = client.patch(
            "/memories/mem_accepted",
            json={
                "actor": _actor_body(),
                "content": "Updated memory.",
            },
        )
        missing_memory = client.post(
            "/memories/missing_memory/archive",
            json={
                "actor": _actor_body(),
                "reason": "Archive reason.",
            },
        )

    assert missing_actor.status_code == 422
    assert missing_actor.json()["error"]["code"] == "validation_error"
    assert missing_actor.json()["error"]["message"] == "local actor context is required"
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["message"] == "reason is required"
    assert missing_memory.status_code == 404
    assert missing_memory.json()["error"]["code"] == "not_found"


def test_memory_mutation_routes_reject_invalid_status_transitions_and_related_ids(
    tmp_path,
) -> None:
    app, _resources = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        review_non_candidate = client.post(
            "/memories/mem_accepted/review",
            json={
                "actor": _actor_body(),
                "decision": "accept",
                "reason": "Review non-candidate.",
            },
        )
        edit_archived = client.patch(
            "/memories/mem_archived",
            json={
                "actor": _actor_body(),
                "content": "Updated archived memory.",
                "reason": "Edit archived memory.",
            },
        )
        wrong_actor_user = client.post(
            "/memories/mem_candidate/archive",
            json={
                "actor": _actor_body(user_id="user_other"),
                "reason": "Archive as wrong user.",
            },
        )
        wrong_character = client.post(
            "/memories/mem_candidate/review",
            json={
                "actor": _actor_body(),
                "decision": "reject",
                "reason": "Wrong character.",
                "character_id": "char_other",
            },
        )

    assert review_non_candidate.status_code == 422
    assert "only candidate memories can be reviewed" in review_non_candidate.text
    assert edit_archived.status_code == 422
    assert "archived memories cannot be edited" in edit_archived.text
    assert wrong_actor_user.status_code == 422
    assert "user_id must match memory user_id" in wrong_actor_user.text
    assert wrong_character.status_code == 422
    assert "character_id must match memory character_id" in wrong_character.text


def _actor_body(
    *,
    user_id: str = "user_001",
    metadata: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "actor_type": "api_user",
        "actor_id": "api-local:reviewer",
        "actor_label": "Local reviewer",
        "user_id": user_id,
        "metadata": metadata or {"entrypoint": "api-test"},
    }


def _seed_api_app(tmp_path):
    resources = create_database_resources(f"sqlite:///{tmp_path / 'api-memory-mutations.db'}")
    with session_scope(resources.session_factory) as session:
        _seed_records(session)
    return create_app(settings=_settings(), database_resources=resources), resources


def _seed_records(session) -> None:
    SourceWorkRepository(session).add(
        SourceWork(
            id="sw_001",
            title="Memory Mutation Work",
            source_type="markdown",
            created_at=NOW,
        )
    )
    CharacterRepository(session).add(
        Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            created_at=NOW,
        )
    )
    CharacterRepository(session).add(
        Character(
            id="char_other",
            source_work_id="sw_001",
            canonical_name="Other Character",
            created_at=NOW,
        )
    )
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="pv_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="Lin Shuang is cautious.",
            created_at=NOW,
        )
    )
    UserRepository(session).add(User(id="user_001", display_name="tester", created_at=NOW))
    UserRepository(session).add(User(id="user_other", display_name="other", created_at=NOW))
    ConversationRepository(session).add(
        Conversation(
            id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_001",
            current_mode=InteractionMode.REALITY_CHAT,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_candidate",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.RELATIONSHIP_MEMORY,
            status=MemoryStatus.CANDIDATE,
            content="Lin Shuang and the user are building trust.",
            importance=0.7,
            reason="Guard queued this relationship note for review.",
            created_at=NOW,
        )
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_accepted",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="User likes night writing.",
            importance=0.8,
            reason="User stated a stable preference.",
            created_at=NOW,
        )
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_archived",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ARCHIVED,
            content="Old memory.",
            importance=0.2,
            reason="Previously archived.",
            created_at=NOW,
        )
    )
