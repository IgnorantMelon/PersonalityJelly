from __future__ import annotations

from contextlib import contextmanager
from typing import Literal

from pydantic import Field
from sqlalchemy.orm import Session

from personality_jelly.application.audit import (
    AuditEntity,
    AuditEventPayload,
    AuditRelatedIds as AuditPayloadRelatedIds,
    AuditResult,
    LocalActorContext,
    build_audit_metadata,
    require_local_actor_context,
)
from personality_jelly.application.conversation_inspection import (
    ConversationInspectionOptions,
    inspect_conversation,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowRelatedIds,
    WorkflowStatus,
    WorkflowWarning,
    start_workflow,
)
from personality_jelly.application.errors import ConflictError
from personality_jelly.application.inspection import ConversationDetail, InspectionModel
from personality_jelly.domain import Conversation, InteractionMode
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.runtime import create_conversation, summarize_conversation
from personality_jelly.storage import ConversationRepository


CONVERSATION_CREATE_WORKFLOW_TYPE = "conversation.create"
CONVERSATION_CREATE_AUDIT_REASON = "local API conversation creation requested"


class ConversationCreateRecord(InspectionModel):
    conversation_id: str
    user_id: str
    character_id: str
    persona_version_id: str
    current_mode: InteractionMode | str


class ConversationCreateResult(InspectionModel):
    request_id: str
    workflow_id: str
    workflow_type: Literal["conversation.create"] = CONVERSATION_CREATE_WORKFLOW_TYPE
    status: WorkflowStatus | str = WorkflowStatus.COMPLETED
    ids: WorkflowRelatedIds
    conversation: ConversationCreateRecord
    audit_event: AuditEventPayload
    warnings: list[WorkflowWarning] = Field(default_factory=list)


def create_conversation_workflow(
    session: Session,
    *,
    user_id: str,
    character_id: str,
    persona_version_id: str | None = None,
    conversation_id: str | None = None,
    interaction_mode: InteractionMode | str = InteractionMode.REALITY_CHAT,
    actor_context: LocalActorContext | None,
    correlation_context: CorrelationContext,
) -> ConversationCreateResult:
    normalized_user_id = _required_text(user_id, field_name="user_id")
    normalized_character_id = _required_text(character_id, field_name="character_id")
    normalized_persona_version_id = _optional_text(
        persona_version_id,
        field_name="persona_version_id",
    )
    normalized_conversation_id = _optional_text(
        conversation_id,
        field_name="conversation_id",
    )
    normalized_mode = InteractionMode(interaction_mode)

    actor = require_local_actor_context(actor_context, require_user_id=True)
    if actor.user_id != normalized_user_id:
        raise ValueError("local actor context user_id must match user_id")

    workflow = start_workflow(
        correlation_context,
        workflow_type=CONVERSATION_CREATE_WORKFLOW_TYPE,
        related_ids=WorkflowRelatedIds(
            user_id=normalized_user_id,
            character_id=normalized_character_id,
            persona_version_id=normalized_persona_version_id,
            conversation_id=normalized_conversation_id,
        ),
    )

    with _conversation_creation_transaction(session):
        if normalized_conversation_id is not None:
            existing = ConversationRepository(session).get(normalized_conversation_id)
            if existing is not None:
                raise ConflictError(
                    f"Conversation {normalized_conversation_id!r} already exists",
                    details={"conversation_id": normalized_conversation_id},
                )

        creation = create_conversation(
            session,
            user_id=normalized_user_id,
            character_id=normalized_character_id,
            persona_version_id=normalized_persona_version_id,
            interaction_mode=normalized_mode,
            conversation_id=normalized_conversation_id,
        )
        conversation = creation.conversation
        ids = WorkflowRelatedIds(
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            conversation_id=conversation.id,
            persona_version_id=conversation.persona_version_id,
        )
        audit_event = _build_conversation_create_audit_event(
            conversation=conversation,
            actor_context=actor,
            workflow=workflow,
        )

    return ConversationCreateResult(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=CONVERSATION_CREATE_WORKFLOW_TYPE,
        status=WorkflowStatus.COMPLETED,
        ids=ids,
        conversation=_conversation_create_record(conversation),
        audit_event=audit_event,
    )


def summarize_conversation_workflow(
    session: Session,
    *,
    conversation_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    max_messages: int = 20,
    inspection_options: ConversationInspectionOptions | None = None,
) -> ConversationDetail:
    summarize_conversation(
        session,
        conversation_id=conversation_id,
        provider=provider,
        model_config=model_config,
        max_messages=max_messages,
    )
    return inspect_conversation(
        session,
        conversation_id,
        options=inspection_options
        or ConversationInspectionOptions(message_limit=max_messages),
    )


@contextmanager
def _conversation_creation_transaction(session: Session):
    if session.in_transaction():
        with session.begin_nested():
            yield
        return

    with session.begin():
        yield


def _build_conversation_create_audit_event(
    *,
    conversation: Conversation,
    actor_context: LocalActorContext,
    workflow,
) -> AuditEventPayload:
    record = _conversation_create_record(conversation)
    return AuditEventPayload(
        actor=actor_context.to_audit_actor(),
        operation=CONVERSATION_CREATE_WORKFLOW_TYPE,
        entity=AuditEntity(
            entity_type="conversation",
            entity_id=conversation.id,
        ),
        related_ids=AuditPayloadRelatedIds(
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            conversation_id=conversation.id,
            persona_version_id=conversation.persona_version_id,
        ),
        reason=actor_context.operation_reason or CONVERSATION_CREATE_AUDIT_REASON,
        before=None,
        after=record.model_dump(mode="json"),
        metadata=build_audit_metadata(
            {"workflow": CONVERSATION_CREATE_WORKFLOW_TYPE},
            actor_context=actor_context,
            correlation=workflow,
            result=AuditResult.SUCCEEDED,
        ),
    )


def _conversation_create_record(conversation: Conversation) -> ConversationCreateRecord:
    return ConversationCreateRecord(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        character_id=conversation.character_id,
        persona_version_id=conversation.persona_version_id,
        current_mode=conversation.current_mode,
    )


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _optional_text(value: object | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name=field_name)
