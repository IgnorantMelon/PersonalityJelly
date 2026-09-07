from __future__ import annotations

from typing import Any

from pydantic import Field

from personality_jelly.application import (
    AuditActorType,
    ConversationCreateResult as ApplicationConversationCreateResult,
    CorrelationContext,
    LocalActorContext,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    WorkflowContext,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    build_workflow_response,
    generate_request_id,
    normalize_idempotency_key,
)
from personality_jelly.application.correlation import MAX_CORRELATION_ID_LENGTH
from personality_jelly.application.inspection import InspectionModel
from personality_jelly.domain import InteractionMode

REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


class WriteRequestCorrelation(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)

    def to_application_context(self) -> CorrelationContext:
        return CorrelationContext(request_id=self.request_id)


class WriteRequestIdBody(InspectionModel):
    request_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    idempotency_key: str | None = Field(
        default=None,
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )


class WriteResponseEnvelope(WorkflowResponseSummary):
    result: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_workflow(
        cls,
        workflow: WorkflowContext,
        *,
        status: WorkflowStatus | str = WorkflowStatus.COMPLETED,
        ids: WorkflowRelatedIds | None = None,
        warnings: list[WorkflowWarning] | None = None,
        result: dict[str, Any] | None = None,
    ) -> "WriteResponseEnvelope":
        summary = build_workflow_response(
            workflow,
            status=status,
            ids=ids,
            warnings=warnings,
        )
        return cls(
            **summary.model_dump(mode="python"),
            result=result or {},
        )


class ConversationCreateActor(InspectionModel):
    actor_type: AuditActorType = AuditActorType.API_USER
    actor_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    actor_label: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    user_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    operation_reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_context(self) -> LocalActorContext:
        return LocalActorContext(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            actor_label=self.actor_label,
            user_id=self.user_id,
            operation_reason=self.operation_reason,
            metadata=self.metadata,
        )


class ConversationCreateRequest(WriteRequestIdBody):
    user_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    character_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    persona_version_id: str | None = Field(
        default=None,
        max_length=MAX_CORRELATION_ID_LENGTH,
    )
    conversation_id: str | None = Field(
        default=None,
        max_length=MAX_CORRELATION_ID_LENGTH,
    )
    interaction_mode: InteractionMode = InteractionMode.REALITY_CHAT
    actor: ConversationCreateActor


class ConversationCreateResponseConversation(InspectionModel):
    conversation_id: str
    user_id: str
    character_id: str
    persona_version_id: str
    current_mode: InteractionMode | str


class ConversationCreateResponseResult(InspectionModel):
    conversation: ConversationCreateResponseConversation
    audit_event: dict[str, Any] | None = None


class ConversationCreateResponse(WriteResponseEnvelope):
    result: ConversationCreateResponseResult

    @classmethod
    def from_application_result(
        cls,
        result: ApplicationConversationCreateResult,
        *,
        audit_event: dict[str, Any] | None = None,
    ) -> "ConversationCreateResponse":
        return cls(
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            workflow_type=result.workflow_type,
            status=result.status,
            ids=result.ids,
            warnings=result.warnings,
            result=ConversationCreateResponseResult(
                conversation=ConversationCreateResponseConversation(
                    **result.conversation.model_dump(mode="python")
                ),
                audit_event=audit_event,
            ),
        )


def resolve_write_request_correlation(
    *,
    header_request_id: object | None = None,
    body_request_id: object | None = None,
) -> WriteRequestCorrelation:
    normalized_header = _normalize_optional_request_id(
        header_request_id,
        source=REQUEST_ID_HEADER,
    )
    normalized_body = _normalize_optional_request_id(
        body_request_id,
        source="body request_id",
    )

    if normalized_header is not None and normalized_body is not None:
        if normalized_header != normalized_body:
            raise ValueError(f"{REQUEST_ID_HEADER} and body request_id must match")
        return WriteRequestCorrelation(request_id=normalized_header)

    return WriteRequestCorrelation(
        request_id=normalized_header or normalized_body or generate_request_id()
    )


def resolve_write_request_idempotency(
    *,
    header_idempotency_key: object | None = None,
    body_idempotency_key: object | None = None,
) -> str | None:
    normalized_header = normalize_idempotency_key(
        header_idempotency_key,
        source=IDEMPOTENCY_KEY_HEADER,
    )
    normalized_body = normalize_idempotency_key(
        body_idempotency_key,
        source="body idempotency_key",
    )

    if normalized_header is not None and normalized_body is not None:
        if normalized_header != normalized_body:
            raise ValueError(
                f"{IDEMPOTENCY_KEY_HEADER} and body idempotency_key must match"
            )
        return normalized_header

    return normalized_header or normalized_body


def _normalize_optional_request_id(value: object | None, *, source: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{source} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{source} must not be blank")
    if len(normalized) > MAX_CORRELATION_ID_LENGTH:
        raise ValueError(
            f"{source} must be at most {MAX_CORRELATION_ID_LENGTH} characters"
        )
    return normalized
