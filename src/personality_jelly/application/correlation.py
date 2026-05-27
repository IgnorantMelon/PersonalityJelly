from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from personality_jelly.application.inspection import InspectionModel
from personality_jelly.domain import WorkflowRun, WorkflowRunLink
from personality_jelly.domain.models import utc_now


MAX_CORRELATION_ID_LENGTH = 128
MAX_WORKFLOW_TYPE_LENGTH = 128
MAX_WORKFLOW_STEP_LENGTH = 128
MAX_WARNING_CODE_LENGTH = 128
MAX_WARNING_MESSAGE_LENGTH = 500


class WorkflowStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class WorkflowRelatedIds(InspectionModel):
    source_work_id: str | None = None
    character_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    persona_version_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    rejected_assistant_message_id: str | None = None
    context_package_id: str | None = None
    critic_report_id: str | None = None
    rejected_critic_report_id: str | None = None
    memory_id: str | None = None
    evaluation_run_id: str | None = None
    retrieval_evaluation_run_id: str | None = None
    audit_event_id: str | None = None
    failure_case_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    evaluation_case_result_ids: list[str] = Field(default_factory=list)
    retrieval_evaluation_case_result_ids: list[str] = Field(default_factory=list)
    audit_event_ids: list[str] = Field(default_factory=list)
    llm_trace_ids: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_related_id(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, list | tuple):
            return [
                _normalize_required_text(
                    item,
                    field_name="related id",
                    max_length=MAX_CORRELATION_ID_LENGTH,
                )
                for item in value
            ]
        return _normalize_required_text(
            value,
            field_name="related id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )


class CorrelationContext(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_type: str | None = Field(default=None, max_length=MAX_WORKFLOW_TYPE_LENGTH)
    status: WorkflowStatus | str | None = None
    related_ids: WorkflowRelatedIds = Field(default_factory=WorkflowRelatedIds)

    @field_validator("request_id", mode="before")
    @classmethod
    def _normalize_request_id(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="request_id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )

    @field_validator("workflow_id", mode="before")
    @classmethod
    def _normalize_optional_workflow_id(cls, value: object) -> object:
        return _normalize_optional_text(
            value,
            field_name="workflow_id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )

    @field_validator("workflow_type", mode="before")
    @classmethod
    def _normalize_optional_workflow_type(cls, value: object) -> object:
        return _normalize_optional_text(
            value,
            field_name="workflow_type",
            max_length=MAX_WORKFLOW_TYPE_LENGTH,
        )


class WorkflowContext(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_type: str = Field(min_length=1, max_length=MAX_WORKFLOW_TYPE_LENGTH)
    status: WorkflowStatus | str = WorkflowStatus.RUNNING
    related_ids: WorkflowRelatedIds = Field(default_factory=WorkflowRelatedIds)

    @field_validator("request_id", "workflow_id", mode="before")
    @classmethod
    def _normalize_correlation_id(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="correlation id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )

    @field_validator("workflow_type", mode="before")
    @classmethod
    def _normalize_workflow_type(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="workflow_type",
            max_length=MAX_WORKFLOW_TYPE_LENGTH,
        )


class WorkflowWarning(InspectionModel):
    code: str = Field(min_length=1, max_length=MAX_WARNING_CODE_LENGTH)
    message: str = Field(min_length=1, max_length=MAX_WARNING_MESSAGE_LENGTH)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code", mode="before")
    @classmethod
    def _normalize_code(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="warning code",
            max_length=MAX_WARNING_CODE_LENGTH,
        )

    @field_validator("message", mode="before")
    @classmethod
    def _normalize_message(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="warning message",
            max_length=MAX_WARNING_MESSAGE_LENGTH,
        )


class WorkflowResponseSummary(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_type: str = Field(min_length=1, max_length=MAX_WORKFLOW_TYPE_LENGTH)
    status: WorkflowStatus | str
    ids: WorkflowRelatedIds = Field(default_factory=WorkflowRelatedIds)
    warnings: list[WorkflowWarning] = Field(default_factory=list)


class WorkflowLinkSpec(InspectionModel):
    entity_type: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=128)
    relation: str = Field(min_length=1, max_length=64)

    @field_validator("entity_type", "entity_id", "relation", mode="before")
    @classmethod
    def _normalize_link_text(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="workflow link field",
            max_length=128,
        )


class ErrorCorrelation(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    workflow_type: str | None = Field(default=None, max_length=MAX_WORKFLOW_TYPE_LENGTH)
    status: WorkflowStatus | str | None = None
    ids: WorkflowRelatedIds = Field(default_factory=WorkflowRelatedIds)
    failed_step: str | None = Field(default=None, max_length=MAX_WORKFLOW_STEP_LENGTH)

    @field_validator("request_id", mode="before")
    @classmethod
    def _normalize_request_id(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_name="request_id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )

    @field_validator("workflow_id", mode="before")
    @classmethod
    def _normalize_optional_workflow_id(cls, value: object) -> object:
        return _normalize_optional_text(
            value,
            field_name="workflow_id",
            max_length=MAX_CORRELATION_ID_LENGTH,
        )

    @field_validator("workflow_type", "failed_step", mode="before")
    @classmethod
    def _normalize_optional_workflow_text(cls, value: object) -> object:
        return _normalize_optional_text(
            value,
            field_name="workflow field",
            max_length=MAX_WORKFLOW_TYPE_LENGTH,
        )


def generate_request_id() -> str:
    return f"req_{uuid4().hex}"


def generate_workflow_id() -> str:
    return f"wf_{uuid4().hex}"


def start_workflow(
    correlation: CorrelationContext,
    *,
    workflow_type: str,
    workflow_id: str | None = None,
    related_ids: WorkflowRelatedIds | None = None,
) -> WorkflowContext:
    return WorkflowContext(
        request_id=correlation.request_id,
        workflow_id=workflow_id or correlation.workflow_id or generate_workflow_id(),
        workflow_type=workflow_type,
        status=WorkflowStatus.RUNNING,
        related_ids=related_ids or correlation.related_ids,
    )


def start_persisted_workflow(
    session: Session,
    correlation: CorrelationContext,
    *,
    workflow_type: str,
    workflow_id: str | None = None,
    related_ids: WorkflowRelatedIds | None = None,
) -> WorkflowContext:
    from personality_jelly.storage import WorkflowRunRepository

    workflow = start_workflow(
        correlation,
        workflow_type=workflow_type,
        workflow_id=workflow_id,
        related_ids=related_ids,
    )
    WorkflowRunRepository(session).add(
        WorkflowRun(
            workflow_id=workflow.workflow_id,
            request_id=workflow.request_id,
            workflow_type=workflow.workflow_type,
            status=WorkflowStatus.RUNNING,
            persisted_ids=_dump_related_ids(workflow.related_ids),
        )
    )
    return workflow


def complete_persisted_workflow(
    session: Session,
    workflow: WorkflowContext,
    *,
    ids: WorkflowRelatedIds,
    links: list[WorkflowLinkSpec] | None = None,
    warnings: list[WorkflowWarning] | None = None,
) -> WorkflowContext:
    from personality_jelly.storage import WorkflowRunRepository

    completed = workflow.model_copy(
        update={
            "status": WorkflowStatus.COMPLETED,
            "related_ids": ids,
        }
    )
    WorkflowRunRepository(session).update_status(
        workflow.workflow_id,
        status=WorkflowStatus.COMPLETED,
        completed_at=utc_now(),
        warnings=[warning.model_dump(mode="json") for warning in warnings or []],
        persisted_ids=_dump_related_ids(ids),
    )
    link_workflow_records(session, workflow.workflow_id, links or [])
    return completed


def fail_persisted_workflow(
    session: Session,
    workflow: WorkflowContext,
    *,
    error_code: str,
    error_details: dict[str, Any] | None = None,
    failed_step: str | None = None,
    ids: WorkflowRelatedIds | None = None,
    links: list[WorkflowLinkSpec] | None = None,
) -> WorkflowContext:
    from personality_jelly.storage import WorkflowRunRepository
    from personality_jelly.application.errors import sanitize_error_details

    failed_ids = ids or workflow.related_ids
    failed = workflow.model_copy(
        update={
            "status": WorkflowStatus.FAILED,
            "related_ids": failed_ids,
        }
    )
    WorkflowRunRepository(session).update_status(
        workflow.workflow_id,
        status=WorkflowStatus.FAILED,
        completed_at=utc_now(),
        error_code=error_code,
        error_details=sanitize_error_details(error_details or {}),
        failed_step=failed_step,
        persisted_ids=_dump_related_ids(failed_ids),
    )
    link_workflow_records(session, workflow.workflow_id, links or [])
    return failed


def partial_persisted_workflow(
    session: Session,
    workflow: WorkflowContext,
    *,
    error_code: str,
    error_details: dict[str, Any] | None = None,
    failed_step: str | None = None,
    ids: WorkflowRelatedIds | None = None,
    links: list[WorkflowLinkSpec] | None = None,
    warnings: list[WorkflowWarning] | None = None,
) -> WorkflowContext:
    from personality_jelly.application.errors import sanitize_error_details
    from personality_jelly.storage import WorkflowRunRepository

    partial_ids = ids or workflow.related_ids
    partial = workflow.model_copy(
        update={
            "status": WorkflowStatus.PARTIAL,
            "related_ids": partial_ids,
        }
    )
    WorkflowRunRepository(session).update_status(
        workflow.workflow_id,
        status=WorkflowStatus.PARTIAL,
        completed_at=utc_now(),
        error_code=error_code,
        error_details=sanitize_error_details(error_details or {}),
        failed_step=failed_step,
        warnings=[warning.model_dump(mode="json") for warning in warnings or []],
        persisted_ids=_dump_related_ids(partial_ids),
    )
    link_workflow_records(session, workflow.workflow_id, links or [])
    return partial


def link_workflow_records(
    session: Session,
    workflow_id: str,
    links: list[WorkflowLinkSpec],
) -> list[WorkflowRunLink]:
    from personality_jelly.core import EntityKind, generate_id
    from personality_jelly.storage import WorkflowRunLinkRepository

    repository = WorkflowRunLinkRepository(session)
    created: list[WorkflowRunLink] = []
    for link in links:
        created.append(
            repository.add(
                WorkflowRunLink(
                    id=generate_id(EntityKind.WORKFLOW_RUN_LINK),
                    workflow_id=workflow_id,
                    entity_type=link.entity_type,
                    entity_id=link.entity_id,
                    relation=link.relation,
                )
            )
        )
    return created


def build_workflow_response(
    workflow: WorkflowContext,
    *,
    status: WorkflowStatus | str = WorkflowStatus.COMPLETED,
    ids: WorkflowRelatedIds | None = None,
    warnings: list[WorkflowWarning] | None = None,
) -> WorkflowResponseSummary:
    return WorkflowResponseSummary(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=workflow.workflow_type,
        status=status,
        ids=ids or workflow.related_ids,
        warnings=warnings or [],
    )


def _dump_related_ids(ids: WorkflowRelatedIds) -> dict[str, Any]:
    return ids.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def build_error_correlation(
    correlation: CorrelationContext | WorkflowContext,
    *,
    status: WorkflowStatus | str | None = None,
    ids: WorkflowRelatedIds | None = None,
    failed_step: str | None = None,
) -> ErrorCorrelation:
    return ErrorCorrelation(
        request_id=correlation.request_id,
        workflow_id=correlation.workflow_id,
        workflow_type=correlation.workflow_type,
        status=status if status is not None else correlation.status,
        ids=ids or correlation.related_ids,
        failed_step=failed_step,
    )


def dump_error_correlation(correlation: ErrorCorrelation) -> dict[str, Any]:
    return correlation.model_dump(
        mode="json",
        exclude_none=True,
        exclude_defaults=True,
    )


def _normalize_required_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


def _normalize_optional_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
) -> object:
    if value is None:
        return None
    return _normalize_required_text(value, field_name=field_name, max_length=max_length)
