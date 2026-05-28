from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field
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
from personality_jelly.application.character_persona_setup import (
    CharacterPersonaSetupResult as CharacterPersonaBuildResult,
    PersonaSetupTraceRecorders,
    build_character_persona,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowLinkSpec,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    complete_persisted_workflow,
    link_workflow_records,
    start_persisted_workflow,
)
from personality_jelly.application.idempotency import (
    IdempotencyContext,
    load_idempotency_replay,
    store_idempotency_replay,
)
from personality_jelly.application.inspection import InspectionModel
from personality_jelly.application.providers import (
    PersonaSetupModelRoleBundle,
    PersonaSetupProviderRoleBundle,
)
from personality_jelly.application.sources import _validate_safe_metadata
from personality_jelly.domain import Character, SourceWork
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.storage import (
    CharacterRepository,
    LLMRawOutputRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
)


CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE = "character_persona.setup"
CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE = 201
CHARACTER_PERSONA_SETUP_AUDIT_REASON = "local API character persona setup requested"

SETUP_PREFLIGHT_STEP = "setup_preflight"
READER_EXTRACT_STEP = "reader_extract"
VERIFIER_VALIDATE_STEP = "verifier_validate"
PERSONA_COMPILE_STEP = "persona_compile"
TERMINAL_AUDIT_STEP = "terminal_audit"
IDEMPOTENCY_RECORD_STEP = "idempotency_record"

_SETUP_ROLE_NAMES = ("reader", "verifier", "persona_compiler")


@dataclass(frozen=True)
class CharacterPersonaSetupWorkflowRequest:
    source_work_id: str
    character_id: str
    provider_roles: PersonaSetupProviderRoleBundle | None
    model_roles: PersonaSetupModelRoleBundle | None
    actor: LocalActorContext | None
    correlation: CorrelationContext | None
    idempotency: IdempotencyContext | None
    max_chunks: int | None = None
    metadata: Mapping[str, Any] | None = field(default_factory=dict)
    replay: CharacterPersonaSetupReplay | None = None


class CharacterPersonaSetupPersistedIds(InspectionModel):
    source_work_id: str
    character_id: str
    candidate_claim_ids: list[str] = Field(default_factory=list)
    evidence_ref_ids: list[str] = Field(default_factory=list)
    verified_claim_ids: list[str] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)
    persona_version_id: str
    llm_trace_ids: list[str] = Field(default_factory=list)
    audit_event_ids: list[str] = Field(default_factory=list)


class CharacterPersonaSetupCounts(InspectionModel):
    candidate_claims: int = Field(ge=0)
    evidence_refs: int = Field(ge=0)
    verified_claims: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    llm_traces: int = Field(ge=0)
    audit_events: int = Field(ge=0)


class CharacterPersonaSetupRedactionFlags(InspectionModel):
    source_text_redacted: bool = True
    chunk_text_redacted: bool = True
    evidence_excerpt_redacted: bool = True
    prompts_redacted: bool = True
    provider_payloads_redacted: bool = True
    provider_config_redacted: bool = True
    raw_outputs_redacted: bool = True


class CharacterPersonaSetupReplay(InspectionModel):
    response_status_code: int = CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE
    replay_payload: dict[str, Any]


class CharacterPersonaSetupWorkflowResult(WorkflowResponseSummary):
    workflow_type: Literal["character_persona.setup"] = CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    status: WorkflowStatus | str = WorkflowStatus.COMPLETED
    persisted_ids: CharacterPersonaSetupPersistedIds
    counts: CharacterPersonaSetupCounts
    redaction: CharacterPersonaSetupRedactionFlags = Field(
        default_factory=CharacterPersonaSetupRedactionFlags
    )
    warnings: list[WorkflowWarning] = Field(default_factory=list)


def run_character_persona_setup_workflow(
    session: Session,
    request: CharacterPersonaSetupWorkflowRequest,
) -> CharacterPersonaSetupWorkflowResult | CharacterPersonaSetupReplay:
    actor = require_local_actor_context(request.actor)
    _validate_safe_metadata(actor.metadata, field_path="actor.metadata")
    metadata = _validate_safe_metadata(dict(request.metadata or {}), field_path="metadata")
    _validate_correlation(request.correlation)
    _validate_idempotency(request.idempotency)
    _validate_max_chunks(request.max_chunks)
    _validate_role_bundles(request.provider_roles, request.model_roles)

    replay = load_idempotency_replay(session, request.idempotency)
    if replay is not None:
        return CharacterPersonaSetupReplay(
            response_status_code=replay.response_status_code,
            replay_payload=replay.replay_payload,
        )

    source_work, character = _preflight_source_character(session, request)

    with _persona_setup_transaction(session):
        workflow = start_persisted_workflow(
            session,
            request.correlation,
            workflow_type=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
            related_ids=WorkflowRelatedIds(
                source_work_id=source_work.id,
                character_id=character.id,
            ),
        )
        link_workflow_records(
            session,
            workflow.workflow_id,
            [
                WorkflowLinkSpec(
                    entity_type="source_work",
                    entity_id=source_work.id,
                    relation="input",
                ),
                WorkflowLinkSpec(
                    entity_type="character",
                    entity_id=character.id,
                    relation="input",
                ),
            ],
        )

        trace_recorders = _build_trace_recorders(session, workflow)

        # Task 02B can split this successful path into staged failure/partial commits.
        setup = build_character_persona(
            session,
            source_work_id=source_work.id,
            character_id=character.id,
            provider_roles=request.provider_roles,
            model_roles=request.model_roles,
            trace_recorders=trace_recorders,
            max_chunks=request.max_chunks,
        )

        llm_trace_ids = _llm_trace_ids_for_workflow(session, workflow.workflow_id)
        persisted_ids = _persisted_ids(setup, llm_trace_ids=llm_trace_ids)
        ids = _related_ids(persisted_ids)
        completed_for_audit = workflow.model_copy(
            update={"status": WorkflowStatus.COMPLETED, "related_ids": ids}
        )
        audit_event = _build_success_audit_event(
            setup=setup,
            persisted_ids=persisted_ids,
            actor_context=actor,
            workflow=completed_for_audit,
            metadata=metadata,
        )
        persist_audit_event(session, audit_event)

        persisted_ids = persisted_ids.model_copy(
            update={"audit_event_ids": [audit_event.id]}
        )
        ids = _related_ids(persisted_ids)
        workflow = complete_persisted_workflow(
            session,
            workflow,
            ids=ids,
            links=_terminal_links(persisted_ids),
        )
        result = _build_result(
            workflow=workflow,
            ids=ids,
            persisted_ids=persisted_ids,
        )
        replay_payload = (
            request.replay.replay_payload
            if request.replay is not None
            else _default_replay_payload(result)
        )
        idempotency_record = store_idempotency_replay(
            session,
            request.idempotency,
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            status=str(result.status),
            response_status_code=(
                request.replay.response_status_code
                if request.replay is not None
                else CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE
            ),
            replay_payload=replay_payload,
            related_ids=_idempotency_related_ids(result),
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


def _validate_correlation(correlation: CorrelationContext | None) -> None:
    if correlation is None:
        raise ValueError("correlation context is required")


def _validate_idempotency(idempotency: IdempotencyContext | None) -> None:
    if idempotency is None:
        raise ValueError("idempotency context is required")
    if idempotency.workflow_type != CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE:
        raise ValueError("idempotency workflow_type must be character_persona.setup")


def _validate_max_chunks(max_chunks: int | None) -> None:
    if max_chunks is None:
        return
    if not isinstance(max_chunks, int) or max_chunks <= 0:
        raise ValueError("max_chunks must be a positive integer")


def _validate_role_bundles(
    provider_roles: PersonaSetupProviderRoleBundle | None,
    model_roles: PersonaSetupModelRoleBundle | None,
) -> None:
    if provider_roles is None or model_roles is None:
        raise ValueError("provider roles and model roles are required")
    for role_name in _SETUP_ROLE_NAMES:
        provider = getattr(provider_roles, role_name, None)
        model_config = getattr(model_roles, role_name, None)
        if provider is None or not callable(getattr(provider, "generate_json", None)):
            raise ValueError(f"{role_name} provider role is required")
        model_name = getattr(model_config, "model", None)
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(f"{role_name} model role is required")


def _preflight_source_character(
    session: Session,
    request: CharacterPersonaSetupWorkflowRequest,
) -> tuple[SourceWork, Character]:
    source_work_id = _normalize_required_id(request.source_work_id, field_name="source_work_id")
    character_id = _normalize_required_id(request.character_id, field_name="character_id")
    source_work = SourceWorkRepository(session).require(source_work_id)
    character = CharacterRepository(session).require(character_id)
    if character.source_work_id != source_work.id:
        raise ValueError(
            f"Character {character.id!r} does not belong to source work {source_work.id!r}"
        )
    return source_work, character


def _normalize_required_id(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _build_trace_recorders(
    session: Session,
    workflow,
) -> PersonaSetupTraceRecorders:
    trace_repository = LLMRawOutputRepository(session)
    related_ids = {
        "source_work_id": workflow.related_ids.source_work_id,
        "character_id": workflow.related_ids.character_id,
    }
    return PersonaSetupTraceRecorders(
        reader=RepositoryLLMTraceRecorder(
            trace_repository,
            request_id=workflow.request_id,
            workflow_id=workflow.workflow_id,
            workflow_step=READER_EXTRACT_STEP,
            related_ids=related_ids,
        ),
        verifier=RepositoryLLMTraceRecorder(
            trace_repository,
            request_id=workflow.request_id,
            workflow_id=workflow.workflow_id,
            workflow_step=VERIFIER_VALIDATE_STEP,
            related_ids=related_ids,
        ),
        persona_compiler=RepositoryLLMTraceRecorder(
            trace_repository,
            request_id=workflow.request_id,
            workflow_id=workflow.workflow_id,
            workflow_step=PERSONA_COMPILE_STEP,
            related_ids=related_ids,
        ),
    )


def _llm_trace_ids_for_workflow(session: Session, workflow_id: str) -> list[str]:
    links = WorkflowRunLinkRepository(session).list_by_workflow(workflow_id)
    return [
        link.entity_id
        for link in links
        if link.entity_type == "llm_raw_output" and link.relation == "trace"
    ]


def _persisted_ids(
    setup: CharacterPersonaBuildResult,
    *,
    llm_trace_ids: list[str],
) -> CharacterPersonaSetupPersistedIds:
    return CharacterPersonaSetupPersistedIds(
        source_work_id=setup.source_work_id,
        character_id=setup.character_id,
        candidate_claim_ids=setup.candidate_claim_ids,
        evidence_ref_ids=setup.evidence_ref_ids,
        verified_claim_ids=setup.verified_claim_ids,
        conflict_ids=setup.conflict_ids,
        persona_version_id=setup.persona_version_id,
        llm_trace_ids=llm_trace_ids,
        audit_event_ids=[],
    )


def _related_ids(persisted_ids: CharacterPersonaSetupPersistedIds) -> WorkflowRelatedIds:
    audit_event_id = (
        persisted_ids.audit_event_ids[0] if persisted_ids.audit_event_ids else None
    )
    return WorkflowRelatedIds(
        source_work_id=persisted_ids.source_work_id,
        character_id=persisted_ids.character_id,
        persona_version_id=persisted_ids.persona_version_id,
        audit_event_id=audit_event_id,
        audit_event_ids=persisted_ids.audit_event_ids,
        llm_trace_ids=persisted_ids.llm_trace_ids,
    )


def _counts(persisted_ids: CharacterPersonaSetupPersistedIds) -> CharacterPersonaSetupCounts:
    return CharacterPersonaSetupCounts(
        candidate_claims=len(persisted_ids.candidate_claim_ids),
        evidence_refs=len(persisted_ids.evidence_ref_ids),
        verified_claims=len(persisted_ids.verified_claim_ids),
        conflicts=len(persisted_ids.conflict_ids),
        llm_traces=len(persisted_ids.llm_trace_ids),
        audit_events=len(persisted_ids.audit_event_ids),
    )


def _build_success_audit_event(
    *,
    setup: CharacterPersonaBuildResult,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    actor_context: LocalActorContext,
    workflow,
    metadata: dict[str, Any],
) -> AuditEventPayload:
    counts = _counts(persisted_ids)
    after = {
        "source_work_id": setup.source_work_id,
        "character_id": setup.character_id,
        "persona_version_id": setup.persona_version_id,
        "counts": counts.model_dump(mode="json"),
        "redaction": CharacterPersonaSetupRedactionFlags().model_dump(mode="json"),
    }
    return AuditEventPayload(
        actor=actor_context.to_audit_actor(),
        operation=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        entity=AuditEntity(entity_type="character", entity_id=setup.character_id),
        related_ids=AuditPayloadRelatedIds(
            source_work_id=setup.source_work_id,
            character_id=setup.character_id,
            persona_version_id=setup.persona_version_id,
        ),
        reason=actor_context.operation_reason or CHARACTER_PERSONA_SETUP_AUDIT_REASON,
        before=None,
        after=after,
        metadata=build_audit_metadata(
            {
                "workflow": CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
                "source_work_id": setup.source_work_id,
                "character_id": setup.character_id,
                "persona_version_id": setup.persona_version_id,
                "client_metadata": metadata,
                "counts": counts.model_dump(mode="json"),
                "source_text_redacted": True,
                "chunk_text_redacted": True,
                "evidence_excerpt_redacted": True,
                "prompts_redacted": True,
                "provider_payloads_redacted": True,
                "provider_config_redacted": True,
                "raw_outputs_redacted": True,
            },
            actor_context=actor_context,
            correlation=workflow,
            result=AuditResult.SUCCEEDED,
        ),
    )


def _terminal_links(
    persisted_ids: CharacterPersonaSetupPersistedIds,
) -> list[WorkflowLinkSpec]:
    links: list[WorkflowLinkSpec] = []
    links.extend(
        WorkflowLinkSpec(
            entity_type="canon_claim",
            entity_id=claim_id,
            relation="candidate_claim",
        )
        for claim_id in persisted_ids.candidate_claim_ids
    )
    links.extend(
        WorkflowLinkSpec(
            entity_type="evidence_ref",
            entity_id=evidence_ref_id,
            relation="evidence",
        )
        for evidence_ref_id in persisted_ids.evidence_ref_ids
    )
    links.extend(
        WorkflowLinkSpec(
            entity_type="canon_claim",
            entity_id=claim_id,
            relation="verified_claim",
        )
        for claim_id in persisted_ids.verified_claim_ids
    )
    links.extend(
        WorkflowLinkSpec(
            entity_type="claim_conflict",
            entity_id=conflict_id,
            relation="conflict",
        )
        for conflict_id in persisted_ids.conflict_ids
    )
    links.append(
        WorkflowLinkSpec(
            entity_type="persona_version",
            entity_id=persisted_ids.persona_version_id,
            relation="created",
        )
    )
    links.extend(
        WorkflowLinkSpec(
            entity_type="audit_event",
            entity_id=audit_event_id,
            relation="audit",
        )
        for audit_event_id in persisted_ids.audit_event_ids
    )
    return links


def _build_result(
    *,
    workflow,
    ids: WorkflowRelatedIds,
    persisted_ids: CharacterPersonaSetupPersistedIds,
) -> CharacterPersonaSetupWorkflowResult:
    return CharacterPersonaSetupWorkflowResult(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        status=WorkflowStatus.COMPLETED,
        ids=ids,
        persisted_ids=persisted_ids,
        counts=_counts(persisted_ids),
        redaction=CharacterPersonaSetupRedactionFlags(),
        warnings=[],
    )


def _default_replay_payload(result: CharacterPersonaSetupWorkflowResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type,
        "status": result.status,
        "ids": result.ids.model_dump(mode="json"),
        "result": {
            "persisted_ids": result.persisted_ids.model_dump(mode="json"),
            "counts": result.counts.model_dump(mode="json"),
            "redaction": result.redaction.model_dump(mode="json"),
        },
        "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
    }


def _idempotency_related_ids(result: CharacterPersonaSetupWorkflowResult) -> dict[str, Any]:
    return {
        **result.ids.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
        **result.persisted_ids.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
    }


@contextmanager
def _persona_setup_transaction(session: Session):
    if session.in_transaction():
        with session.begin_nested():
            yield
        return

    with session.begin():
        yield
