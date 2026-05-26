from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from personality_jelly.api.redaction import (
    REDACTED_AUTH_HEADER,
    REDACTED_PATH,
    REDACTED_PROVIDER_PAYLOAD,
    REDACTED_REASON,
    REDACTED_SECRET,
    REDACTED_USER_TEXT,
    redact_payload,
)
from personality_jelly.application import (
    BATCH_04_AUDIT_PERSISTENCE_DECISION,
    AuditActor,
    AuditActorType,
    AuditEventPayload,
    AuditOperation,
    AuditResult,
    CorrelationContext,
    LocalActorContext,
    build_audit_metadata,
    build_memory_archive_audit_event,
    build_memory_edit_audit_event,
    build_memory_review_audit_event,
    require_local_actor_context,
    require_operation_reason,
    start_workflow,
)
from personality_jelly.domain import Memory, MemoryScope, MemoryStatus


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_memory_review_audit_payload_carries_actor_reason_snapshots_and_related_ids() -> None:
    before = _memory(status=MemoryStatus.CANDIDATE, reason="Queued for review.")
    after = _memory(status=MemoryStatus.ACCEPTED, reason="Review decision accepted: stable.")

    event = build_memory_review_audit_event(
        event_id="audit_review_001",
        actor=AuditActor(actor_type=AuditActorType.CLI_USER, actor_id="cli"),
        before=before,
        after=after,
        reason="User confirmed this is a durable preference.",
        metadata={"request_id": "local-review"},
    )
    payload = event.model_dump(mode="json")

    assert payload["id"] == "audit_review_001"
    assert payload["persistence"] == "payload_only"
    assert payload["actor"] == {"actor_type": "cli_user", "actor_id": "cli"}
    assert payload["operation"] == "memory.review"
    assert payload["entity"] == {"entity_type": "memory", "entity_id": "mem_001"}
    assert payload["related_ids"]["user_id"] == "user_001"
    assert payload["related_ids"]["character_id"] == "char_001"
    assert payload["related_ids"]["conversation_id"] == "conv_001"
    assert payload["reason"] == "User confirmed this is a durable preference."
    assert payload["before"]["status"] == "candidate"
    assert payload["after"]["status"] == "accepted"
    assert payload["after"]["scope"] == "user_memory"
    assert payload["metadata"] == {
        "request_id": "local-review",
        "result": "succeeded",
    }


def test_memory_edit_audit_payload_preserves_content_and_reason_diff() -> None:
    before = _memory(content="User likes night.", reason="Initial curation.")
    after = _memory(
        content="User prefers late-night writing.",
        reason="User corrected this memory.",
    )

    event = build_memory_edit_audit_event(
        actor=AuditActor(actor_type="api_user", actor_id="user_001"),
        before=before,
        after=after,
        reason="Corrected wording after manual review.",
    )

    assert event.operation == "memory.edit"
    assert event.before is not None
    assert event.after is not None
    assert event.before["content"] == "User likes night."
    assert event.after["content"] == "User prefers late-night writing."
    assert event.related_ids.user_id == "user_001"


def test_memory_archive_audit_requires_reason_before_future_service_use() -> None:
    before = _memory(status=MemoryStatus.ACCEPTED)
    after = _memory(status=MemoryStatus.ARCHIVED)

    with pytest.raises(ValidationError):
        build_memory_archive_audit_event(
            actor=AuditActor(actor_type="cli_user", actor_id="cli"),
            before=before,
            after=after,
            reason=" ",
        )

    event = build_memory_archive_audit_event(
        actor=AuditActor(actor_type="cli_user", actor_id="cli"),
        before=before,
        after=after,
        reason="User asked to remove stale memory.",
    )

    assert event.operation == AuditOperation.MEMORY_ARCHIVE
    assert event.reason == "User asked to remove stale memory."
    assert event.after is not None
    assert event.after["status"] == "archived"


def test_memory_audit_rejects_boundary_changes_between_before_and_after() -> None:
    before = _memory()
    after = _memory(character_id="char_other")

    with pytest.raises(ValueError) as error:
        build_memory_review_audit_event(
            actor=AuditActor(actor_type="cli_user", actor_id="cli"),
            before=before,
            after=after,
            reason="Review decision.",
        )

    assert "character_id" in str(error.value)


def test_audit_models_are_strict_and_record_batch04_payload_only_decision() -> None:
    assert BATCH_04_AUDIT_PERSISTENCE_DECISION == "payload_only"

    with pytest.raises(ValidationError):
        AuditActor(actor_type="cli_user", actor_id=" ")

    with pytest.raises(ValidationError):
        AuditEventPayload(
            actor=AuditActor(actor_type="system", actor_id="system"),
            operation="memory.review",
            entity={"entity_type": "memory", "entity_id": "mem_001"},
            reason="Review decision.",
            unexpected=True,
        )


def test_local_actor_context_models_local_attribution_not_auth_identity() -> None:
    actor = LocalActorContext(
        actor_type="api_user",
        actor_id=" api-local:reviewer ",
        actor_label=" Local reviewer ",
        user_id=" user_001 ",
        operation_reason=" Manual memory correction. ",
        metadata={"source": "local-api"},
    )

    assert actor.actor_type == "api_user"
    assert actor.actor_id == "api-local:reviewer"
    assert actor.actor_label == "Local reviewer"
    assert actor.user_id == "user_001"
    assert actor.operation_reason == "Manual memory correction."
    assert actor.to_audit_actor() == AuditActor(
        actor_type=AuditActorType.API_USER,
        actor_id="api-local:reviewer",
    )
    assert require_local_actor_context(actor, require_user_id=True) is actor
    assert require_operation_reason(" Manual review. ") == "Manual review."

    with pytest.raises(ValueError, match="local actor context is required"):
        require_local_actor_context(None)

    with pytest.raises(ValueError, match="user_id is required"):
        require_local_actor_context(
            LocalActorContext(actor_type="cli_user", actor_id="cli"),
            require_user_id=True,
        )

    with pytest.raises(ValueError, match="reason must not be blank"):
        require_operation_reason(" ")

    with pytest.raises(ValidationError):
        LocalActorContext(actor_type="api_user", actor_id=" ")

    with pytest.raises(ValidationError):
        LocalActorContext(
            actor_type="api_user",
            actor_id="api-local:reviewer",
            operation_reason=" ",
        )


def test_manual_memory_audit_accepts_local_actor_and_workflow_correlation() -> None:
    before = _memory(status=MemoryStatus.CANDIDATE)
    after = _memory(status=MemoryStatus.ACCEPTED)
    actor = LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:reviewer",
        actor_label="Local reviewer",
        user_id="user_001",
        operation_reason="Accepted after manual review.",
        metadata={"entrypoint": "local-api"},
    )
    workflow = start_workflow(
        CorrelationContext(request_id="req_memory"),
        workflow_type="memory.review",
        workflow_id="wf_memory",
    )

    event = build_memory_review_audit_event(
        event_id="audit_review_002",
        actor=actor,
        before=before,
        after=after,
        correlation=workflow,
        metadata={"client_note": "review panel decision"},
    )
    payload = event.model_dump(mode="json")

    assert payload["actor"] == {
        "actor_type": "api_user",
        "actor_id": "api-local:reviewer",
    }
    assert payload["reason"] == "Accepted after manual review."
    assert payload["persistence"] == "payload_only"
    assert payload["metadata"] == {
        "client_note": "review panel decision",
        "actor_label": "Local reviewer",
        "actor_user_id": "user_001",
        "actor_metadata": {"entrypoint": "local-api"},
        "request_id": "req_memory",
        "workflow_id": "wf_memory",
        "workflow_type": "memory.review",
        "workflow_status": "running",
        "result": "succeeded",
    }


def test_audit_metadata_sanitizes_never_expose_fields() -> None:
    metadata = build_audit_metadata(
        {
            "api_key": "sk-live-secret",
            "authorization": "Bearer local-token",
            "local_path": "C:\\Users\\figna\\private\\config.toml",
            "provider_response_payload": {"raw": "provider body"},
            "nested": {
                "message": "opened C:\\Users\\figna\\private\\db.sqlite",
            },
        },
        result=AuditResult.FAILED,
    )

    assert metadata["api_key"] == REDACTED_SECRET
    assert metadata["authorization"] == REDACTED_AUTH_HEADER
    assert metadata["local_path"] == REDACTED_PATH
    assert metadata["provider_response_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert metadata["nested"]["message"] == f"opened {REDACTED_PATH}"
    assert metadata["result"] == "failed"
    serialized = _serialized(metadata)
    assert "sk-live-secret" not in serialized
    assert "local-token" not in serialized
    assert "C:\\Users\\figna" not in serialized
    assert "provider body" not in serialized


def test_audit_payload_can_be_redacted_for_safe_response_serialization() -> None:
    before = _memory(
        content="User private note from C:\\Users\\figna\\notes.txt",
        reason="User said the private note directly.",
    )
    after = _memory(
        content="User corrected private note.",
        reason="Manual correction after review.",
    )

    event = build_memory_edit_audit_event(
        actor=LocalActorContext(
            actor_type="api_user",
            actor_id="api-local:reviewer",
            operation_reason="Corrected memory wording.",
            metadata={"api_key": "sk-actor-secret"},
        ),
        before=before,
        after=after,
        metadata={
            "provider_response_payload": {"raw": "provider body"},
            "local_path": "C:\\Users\\figna\\provider\\payload.json",
        },
    )

    redacted = redact_payload(event)

    assert redacted["reason"] == REDACTED_REASON
    assert redacted["before"]["content"] == REDACTED_USER_TEXT
    assert redacted["before"]["reason"] == REDACTED_REASON
    assert redacted["after"]["content"] == REDACTED_USER_TEXT
    assert redacted["after"]["reason"] == REDACTED_REASON
    assert redacted["metadata"]["provider_response_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert redacted["metadata"]["local_path"] == REDACTED_PATH
    assert redacted["metadata"]["actor_metadata"]["api_key"] == REDACTED_SECRET
    serialized = _serialized(redacted)
    assert "C:\\Users\\figna" not in serialized
    assert "sk-actor-secret" not in serialized
    assert "provider body" not in serialized


def _memory(
    *,
    memory_id: str = "mem_001",
    user_id: str = "user_001",
    character_id: str = "char_001",
    conversation_id: str | None = "conv_001",
    scope: MemoryScope = MemoryScope.USER_MEMORY,
    status: MemoryStatus = MemoryStatus.CANDIDATE,
    content: str = "User prefers late-night writing.",
    importance: float = 0.8,
    reason: str = "User stated preference.",
) -> Memory:
    return Memory(
        id=memory_id,
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        scope=scope,
        status=status,
        content=content,
        importance=importance,
        reason=reason,
        created_at=NOW,
    )


def _serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
