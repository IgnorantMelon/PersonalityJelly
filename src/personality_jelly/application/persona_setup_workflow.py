from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from personality_jelly.application.audit import (
    AuditEntity,
    AuditEventPayload,
    AuditRelatedIds as AuditPayloadRelatedIds,
    AuditResult,
    LocalActorContext,
    build_audit_metadata,
    build_workflow_failure_audit_event,
    persist_audit_event,
    require_local_actor_context,
)
from personality_jelly.application.character_persona_setup import (
    PersonaSetupTraceRecorders,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowLinkSpec,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    complete_persisted_workflow,
    fail_persisted_workflow,
    link_workflow_records,
    partial_persisted_workflow,
    start_persisted_workflow,
)
from personality_jelly.application.errors import (
    PartialPersistenceError,
    ProviderFailureError,
    ProviderValidationFailureError,
    WorkflowFailureCode,
    WorkflowFailureDetails,
    build_partial_persistence_details,
    build_provider_failure_details,
    normalize_error,
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
from personality_jelly.domain import Character, ClaimStatus, SourceWork
from personality_jelly.extraction import (
    CanonVerificationResult,
    ExtractionPersistenceResult,
    run_reader_extraction,
    verify_candidate_claims,
)
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.persona import PersonaCompilationResult, compile_persona_version
from personality_jelly.storage import (
    CharacterRepository,
    CanonClaimRepository,
    LLMRawOutputRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
)


CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE = "character_persona.setup"
CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE = 201
CHARACTER_PERSONA_SETUP_PROVIDER_FAILURE_STATUS_CODE = 502
CHARACTER_PERSONA_SETUP_PARTIAL_STATUS_CODE = 500
CHARACTER_PERSONA_SETUP_AUDIT_REASON = "local API character persona setup requested"
CHARACTER_PERSONA_SETUP_RETRY_HINT = (
    "inspect_workflow_and_retry_with_new_idempotency_key"
)

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
    persona_version_id: str | None = None
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
    failure: WorkflowFailureDetails | None = None
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

    workflow = _start_setup_workflow(session, request, source_work, character)
    trace_recorders = _build_trace_recorders(session, workflow)
    persisted_ids = _empty_persisted_ids(source_work, character)

    try:
        extraction = run_reader_extraction(
            session,
            provider=request.provider_roles.reader,
            model_config=request.model_roles.reader,
            character_id=character.id,
            max_chunks=request.max_chunks,
            trace_recorder=trace_recorders.reader,
        )
    except Exception as exc:
        return _terminal_provider_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=persisted_ids,
            failed_step=READER_EXTRACT_STEP,
            exc=exc,
            partial=False,
        )

    persisted_ids = persisted_ids.model_copy(
        update={
            "candidate_claim_ids": [claim.id for claim in extraction.claims],
            "evidence_ref_ids": [evidence.id for evidence in extraction.evidence_refs],
            "llm_trace_ids": _llm_trace_ids_for_workflow(session, workflow.workflow_id),
        }
    )
    if not persisted_ids.candidate_claim_ids:
        return _terminal_validation_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=persisted_ids,
            failed_step=READER_EXTRACT_STEP,
            error_code="no_candidate_claims",
            partial=False,
        )
    link_workflow_records(session, workflow.workflow_id, _reader_links(extraction))
    session.commit()

    try:
        verification = verify_candidate_claims(
            session,
            provider=request.provider_roles.verifier,
            model_config=request.model_roles.verifier,
            character=CharacterRepository(session).require(character.id),
            trace_recorder=trace_recorders.verifier,
        )
    except Exception as exc:
        return _terminal_provider_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
            failed_step=VERIFIER_VALIDATE_STEP,
            exc=exc,
            partial=True,
        )

    persisted_ids = _verification_persisted_ids(
        session,
        workflow=workflow,
        persisted_ids=persisted_ids,
        verification=verification,
    )
    link_workflow_records(session, workflow.workflow_id, _verifier_links(verification))
    session.commit()

    if not persisted_ids.verified_claim_ids:
        return _terminal_validation_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=persisted_ids,
            failed_step=PERSONA_COMPILE_STEP,
            error_code="no_verified_claims",
            partial=True,
        )

    try:
        compilation = compile_persona_version(
            session,
            provider=request.provider_roles.persona_compiler,
            model_config=request.model_roles.persona_compiler,
            character_id=character.id,
            trace_recorder=trace_recorders.persona_compiler,
        )
    except Exception as exc:
        return _terminal_provider_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
            failed_step=PERSONA_COMPILE_STEP,
            exc=exc,
            partial=True,
        )

    return _terminal_success_result(
        session,
        request=request,
        workflow=workflow,
        source_work=source_work,
        character=character,
        compilation=compilation,
        persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
        actor=actor,
        metadata=metadata,
    )


def _start_setup_workflow(
    session: Session,
    request: CharacterPersonaSetupWorkflowRequest,
    source_work: SourceWork,
    character: Character,
):
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
    session.commit()
    return workflow


def _terminal_provider_failure_result(
    session: Session,
    *,
    request: CharacterPersonaSetupWorkflowRequest,
    workflow,
    actor: LocalActorContext,
    metadata: dict[str, Any],
    persisted_ids: CharacterPersonaSetupPersistedIds,
    failed_step: str,
    exc: Exception,
    partial: bool,
) -> CharacterPersonaSetupWorkflowResult:
    if _is_provider_validation_error(exc):
        if partial:
            return _terminal_failure_result(
                session,
                request=request,
                workflow=workflow,
                actor=actor,
                metadata=metadata,
                persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
                status=WorkflowStatus.PARTIAL,
                failed_step=failed_step,
                error_family=WorkflowFailureCode.PARTIAL_PERSISTENCE,
                error_code=str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR),
                detail_cause=str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR),
                rollback_before_terminal=False,
            )
        return _terminal_failure_result(
            session,
            request=request,
            workflow=workflow,
            actor=actor,
            metadata=metadata,
            persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
            status=WorkflowStatus.FAILED,
            failed_step=failed_step,
            error_family=WorkflowFailureCode.PROVIDER_VALIDATION_ERROR,
            error_code=str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR),
            detail_cause=str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR),
            rollback_before_terminal=False,
        )

    return _terminal_failure_result(
        session,
        request=request,
        workflow=workflow,
        actor=actor,
        metadata=metadata,
        persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
        status=WorkflowStatus.PARTIAL if partial else WorkflowStatus.FAILED,
        failed_step=failed_step,
        error_family=(
            WorkflowFailureCode.PARTIAL_PERSISTENCE
            if partial
            else WorkflowFailureCode.PROVIDER_FAILURE
        ),
        error_code=str(WorkflowFailureCode.PROVIDER_FAILURE),
        detail_cause=str(WorkflowFailureCode.PROVIDER_FAILURE),
        rollback_before_terminal=True,
    )


def _terminal_validation_failure_result(
    session: Session,
    *,
    request: CharacterPersonaSetupWorkflowRequest,
    workflow,
    actor: LocalActorContext,
    metadata: dict[str, Any],
    persisted_ids: CharacterPersonaSetupPersistedIds,
    failed_step: str,
    error_code: str,
    partial: bool,
) -> CharacterPersonaSetupWorkflowResult:
    return _terminal_failure_result(
        session,
        request=request,
        workflow=workflow,
        actor=actor,
        metadata=metadata,
        persisted_ids=_refresh_trace_ids(session, workflow, persisted_ids),
        status=WorkflowStatus.PARTIAL if partial else WorkflowStatus.FAILED,
        failed_step=failed_step,
        error_family=(
            WorkflowFailureCode.PARTIAL_PERSISTENCE
            if partial
            else WorkflowFailureCode.PROVIDER_VALIDATION_ERROR
        ),
        error_code=error_code,
        detail_cause=error_code,
        rollback_before_terminal=False,
    )


def _terminal_failure_result(
    session: Session,
    *,
    request: CharacterPersonaSetupWorkflowRequest,
    workflow,
    actor: LocalActorContext,
    metadata: dict[str, Any],
    persisted_ids: CharacterPersonaSetupPersistedIds,
    status: WorkflowStatus,
    failed_step: str,
    error_family: WorkflowFailureCode,
    error_code: str,
    detail_cause: str,
    rollback_before_terminal: bool,
) -> CharacterPersonaSetupWorkflowResult:
    if rollback_before_terminal:
        session.rollback()

    persisted_ids = _refresh_trace_ids(session, workflow, persisted_ids)
    failure = _build_failure_details(
        workflow=workflow,
        persisted_ids=persisted_ids,
        error_family=error_family,
        error_code=error_code,
        failed_step=failed_step,
        detail_cause=detail_cause,
    )
    audit_event = _build_failure_audit_event(
        actor_context=actor,
        workflow=workflow,
        persisted_ids=persisted_ids,
        status=status,
        failure=failure,
        metadata=metadata,
    )
    failure = _build_failure_details(
        workflow=workflow,
        persisted_ids=persisted_ids,
        error_family=error_family,
        error_code=error_code,
        failed_step=failed_step,
        detail_cause=detail_cause,
        audit_event_ids=[audit_event.id],
    )
    audit_event = _build_failure_audit_event(
        actor_context=actor,
        workflow=workflow,
        persisted_ids=persisted_ids,
        status=status,
        failure=failure,
        metadata=metadata,
        event_id=audit_event.id,
    )
    persist_audit_event(session, audit_event)

    persisted_ids = persisted_ids.model_copy(
        update={"audit_event_ids": [audit_event.id]}
    )
    ids = _related_ids(persisted_ids)
    normalized = _normalized_failure(failure)
    result = _build_result(
        workflow=workflow,
        ids=ids,
        persisted_ids=persisted_ids,
        status=status,
        failure=failure,
    )
    workflow_links = _failure_terminal_links(persisted_ids)
    if status == WorkflowStatus.PARTIAL:
        workflow = partial_persisted_workflow(
            session,
            workflow,
            error_code=normalized.code,
            error_details=normalized.details,
            failed_step=failed_step,
            ids=ids,
            links=workflow_links,
        )
    else:
        workflow = fail_persisted_workflow(
            session,
            workflow,
            error_code=normalized.code,
            error_details=normalized.details,
            failed_step=failed_step,
            ids=ids,
            links=workflow_links,
        )
    result = result.model_copy(
        update={
            "workflow_id": workflow.workflow_id,
            "request_id": workflow.request_id,
            "ids": ids,
        }
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
            else _failure_status_code(failure)
        ),
        replay_payload=(
            request.replay.replay_payload
            if request.replay is not None
            else _default_replay_payload(result)
        ),
        related_ids=_idempotency_related_ids(result),
        error_code=normalized.code,
        error_details=normalized.details,
    )
    if idempotency_record is not None:
        idempotency_link = [
            WorkflowLinkSpec(
                entity_type="idempotency_record",
                entity_id=idempotency_record.id,
                relation="idempotency",
            )
        ]
        if status == WorkflowStatus.PARTIAL:
            partial_persisted_workflow(
                session,
                workflow,
                error_code=normalized.code,
                error_details=normalized.details,
                failed_step=failed_step,
                ids=ids,
                links=idempotency_link,
            )
        else:
            fail_persisted_workflow(
                session,
                workflow,
                error_code=normalized.code,
                error_details=normalized.details,
                failed_step=failed_step,
                ids=ids,
                links=idempotency_link,
            )
    session.commit()
    return result


def _terminal_success_result(
    session: Session,
    *,
    request: CharacterPersonaSetupWorkflowRequest,
    workflow,
    source_work: SourceWork,
    character: Character,
    compilation: PersonaCompilationResult,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    actor: LocalActorContext,
    metadata: dict[str, Any],
) -> CharacterPersonaSetupWorkflowResult:
    persisted_ids = persisted_ids.model_copy(
        update={
            "persona_version_id": compilation.persona_version.id,
            "llm_trace_ids": _llm_trace_ids_for_workflow(session, workflow.workflow_id),
        }
    )
    ids = _related_ids(persisted_ids)
    completed_for_audit = workflow.model_copy(
        update={"status": WorkflowStatus.COMPLETED, "related_ids": ids}
    )
    audit_event = _build_success_audit_event(
        source_work=source_work,
        character=character,
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
        links=_success_terminal_links(persisted_ids),
    )
    result = _build_result(
        workflow=workflow,
        ids=ids,
        persisted_ids=persisted_ids,
        status=WorkflowStatus.COMPLETED,
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
    session.commit()
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


def _empty_persisted_ids(
    source_work: SourceWork,
    character: Character,
) -> CharacterPersonaSetupPersistedIds:
    return CharacterPersonaSetupPersistedIds(
        source_work_id=source_work.id,
        character_id=character.id,
    )


def _refresh_trace_ids(
    session: Session,
    workflow,
    persisted_ids: CharacterPersonaSetupPersistedIds,
) -> CharacterPersonaSetupPersistedIds:
    return persisted_ids.model_copy(
        update={"llm_trace_ids": _llm_trace_ids_for_workflow(session, workflow.workflow_id)}
    )


def _verification_persisted_ids(
    session: Session,
    *,
    workflow,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    verification: CanonVerificationResult,
) -> CharacterPersonaSetupPersistedIds:
    verified_claims = CanonClaimRepository(session).list_by_character(
        persisted_ids.character_id,
        status=ClaimStatus.VERIFIED,
    )
    return persisted_ids.model_copy(
        update={
            "verified_claim_ids": [claim.id for claim in verified_claims],
            "conflict_ids": [conflict.id for conflict in verification.conflicts],
            "llm_trace_ids": _llm_trace_ids_for_workflow(session, workflow.workflow_id),
        }
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
    source_work: SourceWork,
    character: Character,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    actor_context: LocalActorContext,
    workflow,
    metadata: dict[str, Any],
) -> AuditEventPayload:
    counts = _counts(persisted_ids)
    after = {
        "source_work_id": source_work.id,
        "character_id": character.id,
        "persona_version_id": persisted_ids.persona_version_id,
        "counts": counts.model_dump(mode="json"),
        "redaction": CharacterPersonaSetupRedactionFlags().model_dump(mode="json"),
    }
    return AuditEventPayload(
        actor=actor_context.to_audit_actor(),
        operation=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        entity=AuditEntity(entity_type="character", entity_id=character.id),
        related_ids=AuditPayloadRelatedIds(
            source_work_id=source_work.id,
            character_id=character.id,
            persona_version_id=persisted_ids.persona_version_id,
        ),
        reason=actor_context.operation_reason or CHARACTER_PERSONA_SETUP_AUDIT_REASON,
        before=None,
        after=after,
        metadata=build_audit_metadata(
            {
                "workflow": CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
                "source_work_id": source_work.id,
                "character_id": character.id,
                "persona_version_id": persisted_ids.persona_version_id,
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


def _build_failure_audit_event(
    *,
    actor_context: LocalActorContext,
    workflow,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    status: WorkflowStatus,
    failure: WorkflowFailureDetails,
    metadata: dict[str, Any],
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_workflow_failure_audit_event(
        actor=actor_context,
        operation=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        entity=AuditEntity(entity_type="character", entity_id=persisted_ids.character_id),
        related_ids=AuditPayloadRelatedIds(
            source_work_id=persisted_ids.source_work_id,
            character_id=persisted_ids.character_id,
            persona_version_id=persisted_ids.persona_version_id,
            llm_trace_id=(
                persisted_ids.llm_trace_ids[-1] if persisted_ids.llm_trace_ids else None
            ),
        ),
        reason=actor_context.operation_reason or CHARACTER_PERSONA_SETUP_AUDIT_REASON,
        metadata={
            "workflow": CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
            "client_metadata": metadata,
            "counts": _counts(persisted_ids).model_dump(mode="json"),
            "redaction": CharacterPersonaSetupRedactionFlags().model_dump(mode="json"),
        },
        correlation=workflow.model_copy(
            update={"status": status, "related_ids": _related_ids(persisted_ids)}
        ),
        result=AuditResult.PARTIAL if status == WorkflowStatus.PARTIAL else AuditResult.FAILED,
        failure_details=failure.model_dump(mode="json", exclude_none=True),
        event_id=event_id,
    )


def _reader_links(extraction: ExtractionPersistenceResult) -> list[WorkflowLinkSpec]:
    links = [
        WorkflowLinkSpec(
            entity_type="canon_claim",
            entity_id=claim.id,
            relation="candidate_claim",
        )
        for claim in extraction.claims
    ]
    links.extend(
        WorkflowLinkSpec(
            entity_type="evidence_ref",
            entity_id=evidence.id,
            relation="evidence",
        )
        for evidence in extraction.evidence_refs
    )
    return links


def _verifier_links(verification: CanonVerificationResult) -> list[WorkflowLinkSpec]:
    links: list[WorkflowLinkSpec] = []
    links.extend(
        WorkflowLinkSpec(
            entity_type="canon_claim",
            entity_id=claim.id,
            relation="verified_claim",
        )
        for claim in verification.updated_claims
        if claim.status == ClaimStatus.VERIFIED
    )
    links.extend(
        WorkflowLinkSpec(
            entity_type="claim_conflict",
            entity_id=conflict.id,
            relation="conflict",
        )
        for conflict in verification.conflicts
    )
    return links


def _success_terminal_links(
    persisted_ids: CharacterPersonaSetupPersistedIds,
) -> list[WorkflowLinkSpec]:
    links: list[WorkflowLinkSpec] = []
    if persisted_ids.persona_version_id is not None:
        links.append(
            WorkflowLinkSpec(
                entity_type="persona_version",
                entity_id=persisted_ids.persona_version_id,
                relation="created",
            )
        )
    links.extend(_failure_terminal_links(persisted_ids))
    return links


def _failure_terminal_links(
    persisted_ids: CharacterPersonaSetupPersistedIds,
) -> list[WorkflowLinkSpec]:
    return [
        WorkflowLinkSpec(
            entity_type="audit_event",
            entity_id=audit_event_id,
            relation="audit",
        )
        for audit_event_id in persisted_ids.audit_event_ids
    ]


def _build_result(
    *,
    workflow,
    ids: WorkflowRelatedIds,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    status: WorkflowStatus | str,
    failure: WorkflowFailureDetails | None = None,
) -> CharacterPersonaSetupWorkflowResult:
    return CharacterPersonaSetupWorkflowResult(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        status=status,
        ids=ids,
        persisted_ids=persisted_ids,
        counts=_counts(persisted_ids),
        failure=failure,
        redaction=CharacterPersonaSetupRedactionFlags(),
        warnings=[],
    )


def _default_replay_payload(result: CharacterPersonaSetupWorkflowResult) -> dict[str, Any]:
    if result.failure is not None:
        normalized = _normalized_failure(result.failure)
        details = dict(normalized.details)
        details["correlation"] = {
            "request_id": result.request_id,
            "workflow_id": result.workflow_id,
            "workflow_type": result.workflow_type,
            "status": str(result.status),
            "ids": result.ids.model_dump(
                mode="json",
                exclude_none=True,
                exclude_defaults=True,
            ),
            "failed_step": result.failure.failed_step,
        }
        return {
            "error": {
                "code": normalized.code,
                "message": normalized.message,
                "details": details,
                "trace_id": (
                    result.failure.llm_trace_ids[-1]
                    if result.failure.llm_trace_ids
                    else None
                ),
            }
        }

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


def _build_failure_details(
    *,
    workflow,
    persisted_ids: CharacterPersonaSetupPersistedIds,
    error_family: WorkflowFailureCode,
    error_code: str,
    failed_step: str,
    detail_cause: str,
    audit_event_ids: list[str] | None = None,
) -> WorkflowFailureDetails:
    details = {
        "cause": detail_cause,
        "counts": _counts(persisted_ids).model_dump(mode="json"),
        "redaction": CharacterPersonaSetupRedactionFlags().model_dump(mode="json"),
    }
    persisted_payload = persisted_ids.model_dump(
        mode="json",
        exclude_none=True,
        exclude_defaults=True,
    )
    if error_family == WorkflowFailureCode.PARTIAL_PERSISTENCE:
        return build_partial_persistence_details(
            failed_step=failed_step,
            error_code=error_code,
            workflow_id=workflow.workflow_id,
            persisted_ids=persisted_payload,
            llm_trace_ids=persisted_ids.llm_trace_ids,
            audit_event_ids=audit_event_ids or [],
            retry_hint=CHARACTER_PERSONA_SETUP_RETRY_HINT,
            details=details,
        )
    return build_provider_failure_details(
        error_family=error_family,
        error_code=error_code,
        failed_step=failed_step,
        workflow_id=workflow.workflow_id,
        persisted_ids=persisted_payload,
        llm_trace_ids=persisted_ids.llm_trace_ids,
        audit_event_ids=audit_event_ids or [],
        retry_hint=CHARACTER_PERSONA_SETUP_RETRY_HINT,
        details=details,
    )


def _normalized_failure(failure: WorkflowFailureDetails):
    if str(failure.error_family) == str(WorkflowFailureCode.PARTIAL_PERSISTENCE):
        return normalize_error(PartialPersistenceError(details=failure))
    if str(failure.error_family) == str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR):
        return normalize_error(ProviderValidationFailureError(details=failure))
    return normalize_error(ProviderFailureError(details=failure))


def _failure_status_code(failure: WorkflowFailureDetails) -> int:
    if str(failure.error_family) == str(WorkflowFailureCode.PARTIAL_PERSISTENCE):
        return CHARACTER_PERSONA_SETUP_PARTIAL_STATUS_CODE
    return CHARACTER_PERSONA_SETUP_PROVIDER_FAILURE_STATUS_CODE


def _is_provider_validation_error(exc: Exception) -> bool:
    return isinstance(exc, ValidationError | ValueError)
