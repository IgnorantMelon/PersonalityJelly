from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from personality_jelly.application.inspection import InspectionModel, MemorySummary
from personality_jelly.domain import Memory
from personality_jelly.domain.models import utc_now


BATCH_04_AUDIT_PERSISTENCE_DECISION: Literal["payload_only"] = "payload_only"


class AuditActorType(StrEnum):
    SYSTEM = "system"
    CLI_USER = "cli_user"
    API_USER = "api_user"
    PROVIDER = "provider"
    WORKSPACE_MEMBER = "workspace_member"


class AuditOperation(StrEnum):
    MEMORY_REVIEW = "memory.review"
    MEMORY_EDIT = "memory.edit"
    MEMORY_ARCHIVE = "memory.archive"
    CANON_CLAIM_REVIEW = "canon_claim.review"
    CONVERSATION_TURN = "conversation.turn"
    BENCHMARK_REVIEW = "benchmark.review"


class AuditActor(InspectionModel):
    actor_type: AuditActorType
    actor_id: str = Field(min_length=1)

    @field_validator("actor_id", mode="before")
    @classmethod
    def _normalize_actor_id(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="actor_id")


class AuditEntity(InspectionModel):
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)

    @field_validator("entity_type", "entity_id", mode="before")
    @classmethod
    def _normalize_entity_text(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="entity field")


class AuditRelatedIds(InspectionModel):
    source_work_id: str | None = None
    character_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    context_package_id: str | None = None
    persona_version_id: str | None = None
    critic_report_id: str | None = None
    llm_trace_id: str | None = None
    evaluation_run_id: str | None = None
    retrieval_evaluation_run_id: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_optional_id(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_required_text(value, field_name="related id")


class AuditEventPayload(InspectionModel):
    id: str = Field(default_factory=lambda: _generate_audit_event_id(), min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    actor: AuditActor
    operation: AuditOperation | str
    entity: AuditEntity
    related_ids: AuditRelatedIds = Field(default_factory=AuditRelatedIds)
    reason: str = Field(min_length=1)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    persistence: Literal["payload_only"] = BATCH_04_AUDIT_PERSISTENCE_DECISION

    @field_validator("id", "operation", "reason", mode="before")
    @classmethod
    def _normalize_required_text_field(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="audit field")


def build_memory_review_audit_event(
    *,
    actor: AuditActor,
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_REVIEW,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        event_id=event_id,
    )


def build_memory_edit_audit_event(
    *,
    actor: AuditActor,
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_EDIT,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        event_id=event_id,
    )


def build_memory_archive_audit_event(
    *,
    actor: AuditActor,
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_ARCHIVE,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        event_id=event_id,
    )


def build_manual_memory_audit_event(
    *,
    operation: AuditOperation | str,
    actor: AuditActor,
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> AuditEventPayload:
    before_snapshot = _memory_snapshot(before)
    after_snapshot = _memory_snapshot(after)
    _validate_same_memory_boundary(before_snapshot, after_snapshot)

    return AuditEventPayload(
        id=event_id if event_id is not None else _generate_audit_event_id(),
        actor=actor,
        operation=operation,
        entity=AuditEntity(
            entity_type="memory",
            entity_id=after_snapshot["id"],
        ),
        related_ids=AuditRelatedIds(
            user_id=after_snapshot["user_id"],
            character_id=after_snapshot["character_id"],
            conversation_id=after_snapshot.get("conversation_id"),
        ),
        reason=reason,
        before=before_snapshot,
        after=after_snapshot,
        metadata=metadata or {},
    )


def _memory_snapshot(memory: Memory | MemorySummary) -> dict[str, Any]:
    return memory.model_dump(mode="json")


def _validate_same_memory_boundary(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> None:
    fields = ("id", "user_id", "character_id", "conversation_id", "scope")
    mismatched_fields = [
        field
        for field in fields
        if before_snapshot.get(field) != after_snapshot.get(field)
    ]
    if mismatched_fields:
        joined_fields = ", ".join(mismatched_fields)
        raise ValueError(f"memory audit before/after snapshots must preserve: {joined_fields}")


def _generate_audit_event_id() -> str:
    return f"audit_{uuid4().hex}"


def _normalize_required_text(value: object, *, field_name: str) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped
