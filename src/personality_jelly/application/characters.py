from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal

from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from personality_jelly.application.audit import (
    AuditEntity,
    AuditEventPayload,
    AuditRelatedIds as AuditPayloadRelatedIds,
    AuditResult,
    LocalActorContext,
    build_audit_metadata,
    persist_audit_event,
    require_local_actor_context,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowLinkSpec,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    complete_persisted_workflow,
    start_persisted_workflow,
)
from personality_jelly.application.errors import ConflictError
from personality_jelly.application.idempotency import (
    IdempotencyContext,
    store_idempotency_replay,
)
from personality_jelly.application.inspection import InspectionModel
from personality_jelly.application.sources import _validate_safe_metadata
from personality_jelly.characters import create_character
from personality_jelly.domain import Character
from personality_jelly.storage import CharacterRepository, SourceWorkRepository


CHARACTER_CREATE_WORKFLOW_TYPE = "character.create"
CHARACTER_CREATE_AUDIT_REASON = "local API character creation requested"
CHARACTER_CREATE_SUCCESS_STATUS_CODE = 201


class CharacterIdentity(InspectionModel):
    character_id: str
    source_work_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    latest_persona_version_id: str | None = None


class CharacterCreateRequest(InspectionModel):
    source_work_id: str = Field(min_length=1, max_length=128)
    canonical_name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    character_id: str | None = Field(default=None, min_length=1, max_length=128)
    actor: LocalActorContext | None
    correlation: CorrelationContext
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_work_id", "canonical_name", "character_id")
    @classmethod
    def _normalize_text_field(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("character create text fields must not be blank")
        return normalized

    @field_validator("aliases", mode="before")
    @classmethod
    def _normalize_alias_list(cls, value: object) -> object:
        if value is None:
            return []
        return value

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_safe_metadata(value, field_path="metadata")


class CharacterCreateReplay(InspectionModel):
    response_status_code: int = CHARACTER_CREATE_SUCCESS_STATUS_CODE
    replay_payload: dict[str, Any]


class CharacterCreateResult(WorkflowResponseSummary):
    workflow_type: Literal["character.create"] = CHARACTER_CREATE_WORKFLOW_TYPE
    status: WorkflowStatus | str = WorkflowStatus.COMPLETED
    character: CharacterIdentity
    audit_event: AuditEventPayload
    warnings: list[WorkflowWarning] = Field(default_factory=list)


def create_character_workflow(
    session: Session,
    request: CharacterCreateRequest,
    *,
    idempotency: IdempotencyContext | None = None,
    replay: CharacterCreateReplay | None = None,
) -> CharacterCreateResult:
    actor = require_local_actor_context(request.actor)
    _validate_safe_metadata(actor.metadata, field_path="actor.metadata")
    _preflight_character_create(session, request)

    with _character_create_transaction(session):
        workflow = start_persisted_workflow(
            session,
            request.correlation,
            workflow_type=CHARACTER_CREATE_WORKFLOW_TYPE,
            related_ids=WorkflowRelatedIds(
                source_work_id=request.source_work_id,
                character_id=request.character_id,
            ),
        )
        try:
            creation = create_character(
                session,
                source_work_id=request.source_work_id,
                canonical_name=request.canonical_name,
                aliases=request.aliases,
                character_id=request.character_id,
            )
        except ValueError as exc:
            if "already exists" in str(exc):
                raise ConflictError(
                    str(exc),
                    details={
                        "source_work_id": request.source_work_id,
                        "canonical_name": request.canonical_name,
                    },
                ) from exc
            raise

        character = creation.character
        ids = _related_ids(character)
        completed_workflow = workflow.model_copy(
            update={
                "status": WorkflowStatus.COMPLETED,
                "related_ids": ids,
            }
        )
        audit_event = _build_character_create_audit_event(
            character=character,
            actor_context=actor,
            workflow=completed_workflow,
            metadata=request.metadata,
        )
        persist_audit_event(session, audit_event)
        ids = _related_ids(character, audit_event=audit_event)
        workflow = complete_persisted_workflow(
            session,
            workflow,
            ids=ids,
            links=_character_create_links(character, audit_event=audit_event),
        )
        result = _build_result(
            workflow=workflow,
            ids=ids,
            character=character,
            audit_event=audit_event,
        )
        idempotency_record = store_idempotency_replay(
            session,
            idempotency,
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            status=str(result.status),
            response_status_code=(
                replay.response_status_code
                if replay is not None
                else CHARACTER_CREATE_SUCCESS_STATUS_CODE
            ),
            replay_payload=(
                replay.replay_payload
                if replay is not None
                else _default_replay_payload(result)
            ),
            related_ids=ids,
        )
        if idempotency_record is not None:
            complete_persisted_workflow(
                session,
                workflow,
                ids=ids,
                links=[
                    WorkflowLinkSpec(
                        entity_type="idempotency_record",
                        entity_id=idempotency_record.id,
                        relation="idempotency",
                    )
                ],
            )

    return result


def _preflight_character_create(session: Session, request: CharacterCreateRequest) -> None:
    SourceWorkRepository(session).require(request.source_work_id)
    repository = CharacterRepository(session)
    if request.character_id is not None and repository.get(request.character_id) is not None:
        raise ConflictError(
            f"Character {request.character_id!r} already exists",
            details={"character_id": request.character_id},
        )
    existing = repository.find_by_source_work_and_name(
        request.source_work_id,
        request.canonical_name,
    )
    if existing is not None:
        raise ConflictError(
            (
                f"Character {request.canonical_name!r} already exists for source work "
                f"{request.source_work_id!r}"
            ),
            details={
                "source_work_id": request.source_work_id,
                "canonical_name": request.canonical_name,
                "character_id": existing.id,
            },
        )


@contextmanager
def _character_create_transaction(session: Session):
    if session.in_transaction():
        with session.begin_nested():
            yield
        return

    with session.begin():
        yield


def _build_character_create_audit_event(
    *,
    character: Character,
    actor_context: LocalActorContext,
    workflow,
    metadata: dict[str, Any],
) -> AuditEventPayload:
    identity = _character_identity(character)
    return AuditEventPayload(
        actor=actor_context.to_audit_actor(),
        operation=CHARACTER_CREATE_WORKFLOW_TYPE,
        entity=AuditEntity(entity_type="character", entity_id=character.id),
        related_ids=AuditPayloadRelatedIds(
            source_work_id=character.source_work_id,
            character_id=character.id,
        ),
        reason=actor_context.operation_reason or CHARACTER_CREATE_AUDIT_REASON,
        before=None,
        after=identity.model_dump(mode="json"),
        metadata=build_audit_metadata(
            {
                "workflow": CHARACTER_CREATE_WORKFLOW_TYPE,
                "source_work_id": character.source_work_id,
                "character_id": character.id,
                "canonical_name": character.canonical_name,
                "alias_count": len(character.aliases),
                "client_metadata": metadata,
                "source_text_redacted": True,
                "source_preview_redacted": True,
                "external_config_redacted": True,
                "instruction_payload_redacted": True,
            },
            actor_context=actor_context,
            correlation=workflow,
            result=AuditResult.SUCCEEDED,
        ),
    )


def _related_ids(
    character: Character,
    *,
    audit_event: AuditEventPayload | None = None,
) -> WorkflowRelatedIds:
    return WorkflowRelatedIds(
        source_work_id=character.source_work_id,
        character_id=character.id,
        audit_event_id=audit_event.id if audit_event is not None else None,
        audit_event_ids=[audit_event.id] if audit_event is not None else [],
        llm_trace_ids=[],
    )


def _character_create_links(
    character: Character,
    *,
    audit_event: AuditEventPayload,
) -> list[WorkflowLinkSpec]:
    return [
        WorkflowLinkSpec(
            entity_type="source_work",
            entity_id=character.source_work_id,
            relation="input",
        ),
        WorkflowLinkSpec(
            entity_type="character",
            entity_id=character.id,
            relation="created",
        ),
        WorkflowLinkSpec(
            entity_type="audit_event",
            entity_id=audit_event.id,
            relation="audit",
        ),
    ]


def _build_result(
    *,
    workflow,
    ids: WorkflowRelatedIds,
    character: Character,
    audit_event: AuditEventPayload,
) -> CharacterCreateResult:
    return CharacterCreateResult(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=CHARACTER_CREATE_WORKFLOW_TYPE,
        status=WorkflowStatus.COMPLETED,
        ids=ids,
        warnings=[],
        character=_character_identity(character),
        audit_event=audit_event,
    )


def _character_identity(character: Character) -> CharacterIdentity:
    return CharacterIdentity(
        character_id=character.id,
        source_work_id=character.source_work_id,
        canonical_name=character.canonical_name,
        aliases=list(character.aliases),
        latest_persona_version_id=None,
    )


def _default_replay_payload(result: CharacterCreateResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type,
        "status": result.status,
        "ids": result.ids.model_dump(mode="json"),
        "result": {
            "character": result.character.model_dump(mode="json"),
            "audit_event": _redacted_audit_event_payload(result.audit_event),
        },
        "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
    }


def _redacted_audit_event_payload(audit_event: AuditEventPayload) -> dict[str, Any]:
    payload = audit_event.model_dump(mode="json")
    if "reason" in payload:
        payload["reason"] = "[redacted:reason]"
    return payload
