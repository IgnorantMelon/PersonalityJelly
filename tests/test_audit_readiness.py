from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from personality_jelly.application import (
    BATCH_04_AUDIT_PERSISTENCE_DECISION,
    AuditActor,
    AuditActorType,
    AuditEventPayload,
    AuditOperation,
    build_memory_archive_audit_event,
    build_memory_edit_audit_event,
    build_memory_review_audit_event,
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
    assert payload["metadata"] == {"request_id": "local-review"}


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
