from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field
from sqlalchemy.orm import Session

from personality_jelly.application.audit import (
    AuditEventPayload,
    LocalActorContext,
    build_memory_archive_audit_event,
    build_memory_edit_audit_event,
    build_memory_review_audit_event,
    require_local_actor_context,
    require_operation_reason,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowContext,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    start_workflow,
)
from personality_jelly.application.inspection import (
    InspectionModel,
    MemorySummary,
    get_memory_detail,
)
from personality_jelly.domain import Memory, MemoryStatus
from personality_jelly.storage import MemoryRepository


class MemoryReviewDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class ManualMemoryMutationRequest(InspectionModel):
    memory_id: str = Field(min_length=1)
    reason: str | None = None
    actor: LocalActorContext | None = None
    correlation: CorrelationContext
    user_id: str | None = None
    character_id: str | None = None
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualMemoryReviewRequest(ManualMemoryMutationRequest):
    decision: MemoryReviewDecision


class ManualMemoryEditRequest(ManualMemoryMutationRequest):
    content: str | None = None


class ManualMemoryArchiveRequest(ManualMemoryMutationRequest):
    pass


class ManualMemoryMutationResult(WorkflowResponseSummary):
    memory: MemorySummary
    audit_event: AuditEventPayload


def review_memory_workflow(
    session: Session,
    request: ManualMemoryReviewRequest,
) -> ManualMemoryMutationResult:
    workflow = start_workflow(
        request.correlation,
        workflow_type="memory.review",
        related_ids=WorkflowRelatedIds(memory_id=request.memory_id),
    )
    actor = require_local_actor_context(request.actor, require_user_id=True)
    reason = require_operation_reason(request.reason)
    repository = MemoryRepository(session)
    before = repository.require(request.memory_id)
    _validate_memory_related_ids(before, actor=actor, request=request)

    target_status = (
        MemoryStatus.ACCEPTED
        if request.decision == MemoryReviewDecision.ACCEPT
        else MemoryStatus.REJECTED
    )
    after = repository.review_candidate(before.id, status=target_status, reason=reason)
    return _build_result(
        session,
        workflow=workflow,
        memory=after,
        audit_event=build_memory_review_audit_event(
            actor=actor,
            before=before,
            after=after,
            reason=reason,
            metadata={**request.metadata, "decision": str(request.decision)},
            correlation=_completed_workflow(workflow, _related_ids(after)),
        ),
    )


def edit_memory_workflow(
    session: Session,
    request: ManualMemoryEditRequest,
) -> ManualMemoryMutationResult:
    workflow = start_workflow(
        request.correlation,
        workflow_type="memory.edit",
        related_ids=WorkflowRelatedIds(memory_id=request.memory_id),
    )
    actor = require_local_actor_context(request.actor, require_user_id=True)
    reason = require_operation_reason(request.reason)
    content = _require_text(request.content, field_name="content")
    repository = MemoryRepository(session)
    before = repository.require(request.memory_id)
    _validate_memory_related_ids(before, actor=actor, request=request)
    if before.status == MemoryStatus.ARCHIVED:
        raise ValueError("archived memories cannot be edited")

    after = repository.update_content(before.id, content=content, reason=reason)
    return _build_result(
        session,
        workflow=workflow,
        memory=after,
        audit_event=build_memory_edit_audit_event(
            actor=actor,
            before=before,
            after=after,
            reason=reason,
            metadata=request.metadata,
            correlation=_completed_workflow(workflow, _related_ids(after)),
        ),
    )


def archive_memory_workflow(
    session: Session,
    request: ManualMemoryArchiveRequest,
) -> ManualMemoryMutationResult:
    workflow = start_workflow(
        request.correlation,
        workflow_type="memory.archive",
        related_ids=WorkflowRelatedIds(memory_id=request.memory_id),
    )
    actor = require_local_actor_context(request.actor, require_user_id=True)
    reason = require_operation_reason(request.reason)
    repository = MemoryRepository(session)
    before = repository.require(request.memory_id)
    _validate_memory_related_ids(before, actor=actor, request=request)
    if before.status == MemoryStatus.ARCHIVED:
        raise ValueError("memory is already archived")

    after = repository.update_status(before.id, status=MemoryStatus.ARCHIVED)
    return _build_result(
        session,
        workflow=workflow,
        memory=after,
        audit_event=build_memory_archive_audit_event(
            actor=actor,
            before=before,
            after=after,
            reason=reason,
            metadata=request.metadata,
            correlation=_completed_workflow(workflow, _related_ids(after)),
        ),
    )


def _build_result(
    session: Session,
    *,
    workflow: WorkflowContext,
    memory: Memory,
    audit_event: AuditEventPayload,
) -> ManualMemoryMutationResult:
    ids = _related_ids(memory, audit_event=audit_event)
    completed = _completed_workflow(workflow, ids)
    return ManualMemoryMutationResult(
        request_id=completed.request_id,
        workflow_id=completed.workflow_id,
        workflow_type=completed.workflow_type,
        status=WorkflowStatus.COMPLETED,
        ids=ids,
        memory=get_memory_detail(session, memory.id),
        audit_event=audit_event,
    )


def _completed_workflow(
    workflow: WorkflowContext,
    ids: WorkflowRelatedIds,
) -> WorkflowContext:
    return workflow.model_copy(
        update={
            "status": WorkflowStatus.COMPLETED,
            "related_ids": ids,
        }
    )


def _related_ids(
    memory: Memory,
    *,
    audit_event: AuditEventPayload | None = None,
) -> WorkflowRelatedIds:
    return WorkflowRelatedIds(
        user_id=memory.user_id,
        character_id=memory.character_id,
        conversation_id=memory.conversation_id,
        memory_id=memory.id,
        memory_ids=[memory.id],
        audit_event_id=audit_event.id if audit_event is not None else None,
        audit_event_ids=[audit_event.id] if audit_event is not None else [],
    )


def _validate_memory_related_ids(
    memory: Memory,
    *,
    actor: LocalActorContext,
    request: ManualMemoryMutationRequest,
) -> None:
    if actor.user_id != memory.user_id:
        raise ValueError("local actor context user_id must match memory user_id")
    _validate_optional_related_id(
        "user_id",
        requested=request.user_id,
        actual=memory.user_id,
    )
    _validate_optional_related_id(
        "character_id",
        requested=request.character_id,
        actual=memory.character_id,
    )
    _validate_optional_related_id(
        "conversation_id",
        requested=request.conversation_id,
        actual=memory.conversation_id,
    )


def _validate_optional_related_id(
    field_name: str,
    *,
    requested: str | None,
    actual: str | None,
) -> None:
    if requested is None:
        return
    normalized = _require_text(requested, field_name=field_name)
    if normalized != actual:
        raise ValueError(f"{field_name} must match memory {field_name}")


def _require_text(value: str | None, *, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped
