from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from personality_jelly.api.character_schemas import (
    CharacterCreateRequestBody,
    CharacterCreateResponse,
)
from personality_jelly.api.dependencies import get_session, get_settings, get_write_session
from personality_jelly.api.errors import build_error_envelope
from personality_jelly.api.memory_mutation_schemas import (
    MemoryArchiveRequestBody,
    MemoryEditRequestBody,
    MemoryReviewRequestBody,
)
from personality_jelly.api.persona_setup_schemas import (
    PersonaSetupProviderRequest,
    PersonaSetupRunRequestBody,
    PersonaSetupRunResponse,
)
from personality_jelly.api.redaction import redact_payload
from personality_jelly.api.schemas import (
    IDEMPOTENCY_KEY_HEADER,
    REQUEST_ID_HEADER,
    WriteResponseEnvelope,
    resolve_write_request_correlation,
    resolve_write_request_idempotency,
)
from personality_jelly.application import (
    CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE,
    CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
    CHARACTER_CREATE_SUCCESS_STATUS_CODE,
    CHARACTER_CREATE_WORKFLOW_TYPE,
    CharacterPersonaSetupReplay,
    CharacterPersonaSetupWorkflowResult,
    CharacterDetail,
    ClaimSummary,
    ConflictError,
    CorrelationContext,
    IdempotencyContext,
    InspectionListResult,
    ManualMemoryArchiveRequest,
    ManualMemoryEditRequest,
    ManualMemoryMutationResult,
    ManualMemoryReviewRequest,
    MemorySummary,
    PartialPersistenceError,
    PersonaSetupModelRoleBundle,
    ProviderFailureError,
    ProviderValidationFailureError,
    NormalizedError,
    SourceChunkDetail,
    WorkflowFailureCode,
    WorkflowFailureError,
    WorkflowStatus,
    archive_memory_workflow,
    build_error_correlation,
    build_idempotency_context,
    create_character_workflow,
    edit_memory_workflow,
    get_character_detail,
    get_claim_detail,
    get_memory_detail,
    get_source_chunk_detail,
    list_characters,
    list_claims,
    list_memories,
    load_idempotency_replay,
    normalize_error,
    resolve_persona_setup_provider,
    review_memory_workflow,
    run_character_persona_setup_workflow,
    store_idempotency_replay,
)
from personality_jelly.core import Settings
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryScope, MemoryStatus
from personality_jelly.testing import StubProvider

router = APIRouter(tags=["characters"])


@router.post(
    "/characters",
    response_model=CharacterCreateResponse,
    status_code=CHARACTER_CREATE_SUCCESS_STATUS_CODE,
)
def post_character(
    request: CharacterCreateRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    header_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> CharacterCreateResponse | JSONResponse:
    correlation: CorrelationContext | None = None
    try:
        write_correlation = resolve_write_request_correlation(
            header_request_id=header_request_id,
            body_request_id=request.request_id,
        )
        correlation = write_correlation.to_application_context()
        idempotency = _character_create_idempotency_context(
            request,
            header_idempotency_key=header_idempotency_key,
        )
        replay = load_idempotency_replay(session, idempotency)
        if replay is not None:
            return JSONResponse(
                status_code=replay.response_status_code,
                content=replay.replay_payload,
            )
        result = create_character_workflow(
            session,
            request.to_application_request(correlation),
            idempotency=idempotency,
        )
    except Exception as error:
        return _character_create_error_response(error, correlation=correlation)

    return CharacterCreateResponse.model_validate(
        redact_payload(CharacterCreateResponse.from_application_result(result))
    )


@router.get("/characters", response_model=InspectionListResult)
def get_characters(
    source_work_id: Annotated[str, Query(min_length=1)],
    session: Annotated[Session, Depends(get_session)],
) -> InspectionListResult:
    return list_characters(session, source_work_id=source_work_id)


@router.get("/characters/{character_id}", response_model=CharacterDetail)
def get_character(
    character_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> CharacterDetail:
    return get_character_detail(session, character_id, expand_evidence_chunks=True)


@router.post(
    "/characters/{character_id}/persona-setup-runs",
    response_model=PersonaSetupRunResponse,
    status_code=CHARACTER_PERSONA_SETUP_SUCCESS_STATUS_CODE,
)
def post_character_persona_setup_run(
    character_id: Annotated[str, Path(min_length=1)],
    request: PersonaSetupRunRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    header_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> PersonaSetupRunResponse | JSONResponse:
    correlation: CorrelationContext | None = None
    try:
        normalized_character_id = _normalize_path_character_id(character_id)
        request.validate_path_character_id(normalized_character_id)
        write_correlation = resolve_write_request_correlation(
            header_request_id=header_request_id,
            body_request_id=request.request_id,
        )
        correlation = write_correlation.to_application_context()
        idempotency = _required_persona_setup_idempotency_context(
            request,
            character_id=normalized_character_id,
            header_idempotency_key=header_idempotency_key,
        )
        replay = load_idempotency_replay(session, idempotency)
        if replay is not None:
            return JSONResponse(
                status_code=replay.response_status_code,
                content=replay.replay_payload,
            )
        provider_roles, model_roles = _resolve_persona_setup_role_bundles(
            request.provider,
            settings=settings,
        )
        result = run_character_persona_setup_workflow(
            session,
            request.to_application_request(
                character_id=normalized_character_id,
                correlation=correlation,
                idempotency=idempotency,
                provider_roles=provider_roles,
                model_roles=model_roles,
            ),
        )
    except Exception as error:
        return _persona_setup_exception_response(error, correlation=correlation)

    if isinstance(result, CharacterPersonaSetupReplay):
        return JSONResponse(
            status_code=result.response_status_code,
            content=result.replay_payload,
        )

    if result.failure is not None or result.status != WorkflowStatus.COMPLETED:
        return _persona_setup_result_error_response(result)

    return PersonaSetupRunResponse.model_validate(
        redact_payload(PersonaSetupRunResponse.from_application_result(result))
    )


@router.get("/claims", response_model=InspectionListResult)
def get_claims(
    character_id: Annotated[str, Query(min_length=1)],
    session: Annotated[Session, Depends(get_session)],
    status: ClaimStatus | None = None,
    claim_type: ClaimType | None = None,
) -> InspectionListResult:
    return list_claims(
        session,
        character_id,
        status=status,
        claim_type=claim_type,
        expand_evidence=True,
        expand_chunks=True,
    )


@router.get("/claims/{claim_id}", response_model=ClaimSummary)
def get_claim(
    claim_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> ClaimSummary:
    return get_claim_detail(session, claim_id, expand_chunks=True)


@router.get("/memories", response_model=InspectionListResult)
def get_memories(
    user_id: Annotated[str, Query(min_length=1)],
    character_id: Annotated[str, Query(min_length=1)],
    session: Annotated[Session, Depends(get_session)],
    scope: MemoryScope | None = None,
    status: MemoryStatus | None = None,
) -> InspectionListResult:
    return list_memories(
        session,
        user_id,
        character_id,
        scope=scope,
        status=status,
    )


@router.get("/memories/{memory_id}", response_model=MemorySummary)
def get_memory(
    memory_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> MemorySummary:
    return get_memory_detail(session, memory_id)


@router.post("/memories/{memory_id}/review", response_model=WriteResponseEnvelope)
def review_memory(
    memory_id: str,
    body: MemoryReviewRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> WriteResponseEnvelope | JSONResponse:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
    idempotency = _memory_mutation_idempotency_context(
        body,
        memory_id=memory_id,
        workflow_type="memory.review",
        header_idempotency_key=header_idempotency_key,
    )
    replay = load_idempotency_replay(session, idempotency)
    if replay is not None:
        return JSONResponse(
            status_code=replay.response_status_code,
            content=replay.replay_payload,
        )
    result = review_memory_workflow(
        session,
        ManualMemoryReviewRequest(
            memory_id=memory_id,
            decision=body.decision,
            reason=body.reason,
            actor=_application_actor(body),
            correlation=correlation,
            user_id=body.user_id,
            character_id=body.character_id,
            conversation_id=body.conversation_id,
            metadata=body.metadata,
        ),
    )
    return _memory_mutation_response(session, result, idempotency=idempotency)


@router.patch("/memories/{memory_id}", response_model=WriteResponseEnvelope)
def edit_memory(
    memory_id: str,
    body: MemoryEditRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> WriteResponseEnvelope | JSONResponse:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
    idempotency = _memory_mutation_idempotency_context(
        body,
        memory_id=memory_id,
        workflow_type="memory.edit",
        header_idempotency_key=header_idempotency_key,
    )
    replay = load_idempotency_replay(session, idempotency)
    if replay is not None:
        return JSONResponse(
            status_code=replay.response_status_code,
            content=replay.replay_payload,
        )
    result = edit_memory_workflow(
        session,
        ManualMemoryEditRequest(
            memory_id=memory_id,
            content=body.content,
            reason=body.reason,
            actor=_application_actor(body),
            correlation=correlation,
            user_id=body.user_id,
            character_id=body.character_id,
            conversation_id=body.conversation_id,
            metadata=body.metadata,
        ),
    )
    return _memory_mutation_response(session, result, idempotency=idempotency)


@router.post("/memories/{memory_id}/archive", response_model=WriteResponseEnvelope)
def archive_memory(
    memory_id: str,
    body: MemoryArchiveRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> WriteResponseEnvelope | JSONResponse:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
    idempotency = _memory_mutation_idempotency_context(
        body,
        memory_id=memory_id,
        workflow_type="memory.archive",
        header_idempotency_key=header_idempotency_key,
    )
    replay = load_idempotency_replay(session, idempotency)
    if replay is not None:
        return JSONResponse(
            status_code=replay.response_status_code,
            content=replay.replay_payload,
        )
    result = archive_memory_workflow(
        session,
        ManualMemoryArchiveRequest(
            memory_id=memory_id,
            reason=body.reason,
            actor=_application_actor(body),
            correlation=correlation,
            user_id=body.user_id,
            character_id=body.character_id,
            conversation_id=body.conversation_id,
            metadata=body.metadata,
        ),
    )
    return _memory_mutation_response(session, result, idempotency=idempotency)


@router.get("/source-chunks/{chunk_id}", response_model=SourceChunkDetail)
def get_source_chunk(
    chunk_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> SourceChunkDetail:
    return get_source_chunk_detail(session, chunk_id)


def _required_persona_setup_idempotency_context(
    request: PersonaSetupRunRequestBody,
    *,
    character_id: str,
    header_idempotency_key: object | None,
) -> IdempotencyContext:
    if header_idempotency_key is None:
        raise ValueError(f"{IDEMPOTENCY_KEY_HEADER} is required")

    idempotency_key = resolve_write_request_idempotency(
        header_idempotency_key=header_idempotency_key,
        body_idempotency_key=request.idempotency_key,
    )
    if idempotency_key is None:
        raise ValueError(f"{IDEMPOTENCY_KEY_HEADER} is required")

    idempotency = build_idempotency_context(
        workflow_type=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        idempotency_key=idempotency_key,
        request_payload=request.idempotency_payload(character_id=character_id),
    )
    if idempotency is None:
        raise ValueError(f"{IDEMPOTENCY_KEY_HEADER} is required")
    return idempotency


def _resolve_persona_setup_role_bundles(
    provider_request: PersonaSetupProviderRequest,
    *,
    settings: Settings,
):
    effective_settings = (
        settings.model_copy(update={"llm_model": provider_request.model})
        if provider_request.model is not None
        else settings
    )
    provider_roles, model_roles = resolve_persona_setup_provider(
        provider_request.source,
        settings=effective_settings,
        stub_provider_factory=StubProvider,
    )
    return provider_roles, _apply_persona_setup_model_labels(
        model_roles,
        provider_request=provider_request,
    )


def _apply_persona_setup_model_labels(
    model_roles: PersonaSetupModelRoleBundle,
    *,
    provider_request: PersonaSetupProviderRequest,
) -> PersonaSetupModelRoleBundle:
    role_models = provider_request.roles.model_labels()
    bundle_model = provider_request.model

    def _model_for_role(role_name: str, current_model: str) -> str:
        return role_models.get(role_name) or bundle_model or current_model

    return PersonaSetupModelRoleBundle(
        reader=model_roles.reader.model_copy(
            update={"model": _model_for_role("reader", model_roles.reader.model)}
        ),
        verifier=model_roles.verifier.model_copy(
            update={"model": _model_for_role("verifier", model_roles.verifier.model)}
        ),
        persona_compiler=model_roles.persona_compiler.model_copy(
            update={
                "model": _model_for_role(
                    "persona_compiler",
                    model_roles.persona_compiler.model,
                )
            }
        ),
    )


def _normalize_path_character_id(character_id: str) -> str:
    normalized = character_id.strip()
    if not normalized:
        raise ValueError("path character_id must not be blank")
    return normalized


def _persona_setup_result_error_response(
    result: CharacterPersonaSetupWorkflowResult,
) -> JSONResponse:
    status_code = _persona_setup_result_status_code(result)
    envelope = build_error_envelope(
        _normalize_persona_setup_failure_result(result),
        correlation=build_error_correlation(
            CorrelationContext(
                request_id=result.request_id,
                workflow_id=result.workflow_id,
                workflow_type=result.workflow_type,
                status=result.status,
                related_ids=result.ids,
            ),
            status=result.status,
            ids=result.ids,
            failed_step=result.failure.failed_step if result.failure is not None else None,
        ),
        trace_id=_persona_setup_trace_id(result),
    )
    return JSONResponse(
        status_code=status_code,
        content=redact_payload(envelope),
    )


def _persona_setup_result_status_code(result: CharacterPersonaSetupWorkflowResult) -> int:
    if result.failure is None:
        return 500
    if str(result.failure.error_family) == str(WorkflowFailureCode.PARTIAL_PERSISTENCE):
        return 500
    if str(result.failure.error_family) == str(WorkflowFailureCode.PROVIDER_FAILURE):
        return 502
    if str(result.failure.error_family) == str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR):
        return 502
    return 500


def _normalize_persona_setup_failure_result(
    result: CharacterPersonaSetupWorkflowResult,
) -> NormalizedError:
    failure = result.failure
    if failure is None:
        return normalize_error(RuntimeError("persona setup did not complete"))
    if str(failure.error_family) == str(WorkflowFailureCode.PARTIAL_PERSISTENCE):
        return normalize_error(PartialPersistenceError(details=failure))
    if str(failure.error_family) == str(WorkflowFailureCode.PROVIDER_VALIDATION_ERROR):
        return normalize_error(ProviderValidationFailureError(details=failure))
    return normalize_error(ProviderFailureError(details=failure))


def _persona_setup_trace_id(
    result: CharacterPersonaSetupWorkflowResult,
) -> str | None:
    if result.failure is None or not result.failure.llm_trace_ids:
        return None
    return result.failure.llm_trace_ids[-1]


def _persona_setup_exception_response(
    error: Exception,
    *,
    correlation: CorrelationContext | None,
) -> JSONResponse:
    status_code = _persona_setup_exception_status_code(error)
    error_correlation = (
        build_error_correlation(
            correlation,
            status=WorkflowStatus.FAILED,
            failed_step=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
        )
        if correlation is not None
        else None
    )
    envelope = build_error_envelope(
        _normalize_persona_setup_exception(error),
        correlation=error_correlation,
    )
    return JSONResponse(
        status_code=status_code,
        content=redact_payload(envelope),
    )


def _persona_setup_exception_status_code(error: Exception) -> int:
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, LookupError):
        return 404
    if isinstance(error, WorkflowFailureError):
        if error.normalized_code == WorkflowFailureCode.RETRYABLE_CONFLICT:
            return 409
        if error.normalized_code == WorkflowFailureCode.PARTIAL_PERSISTENCE:
            return 500
        return 502
    if isinstance(error, ValueError):
        return 422
    if isinstance(error, ValidationError):
        return 422
    return 500


def _normalize_persona_setup_exception(error: Exception) -> NormalizedError:
    if not isinstance(error, ValidationError):
        return normalize_error(error)
    details = []
    for item in error.errors(include_input=False, include_context=False):
        details.append(
            {
                "loc": list(item.get("loc", [])),
                "msg": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
        )
    message = details[0]["msg"] if details else "Request validation failed"
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return NormalizedError(
        code="validation_error",
        message=message,
        details={"errors": details},
    )


def _application_actor(
    body: MemoryArchiveRequestBody | MemoryEditRequestBody | MemoryReviewRequestBody,
):
    if body.actor is None:
        return None
    return body.actor.to_application_actor(operation_reason=body.reason)


def _memory_mutation_response(
    session: Session,
    result: ManualMemoryMutationResult,
    *,
    idempotency: IdempotencyContext | None,
) -> WriteResponseEnvelope:
    response = WriteResponseEnvelope(
        request_id=result.request_id,
        workflow_id=result.workflow_id,
        workflow_type=result.workflow_type,
        status=result.status,
        ids=result.ids,
        warnings=result.warnings,
        result=redact_payload(
            {
                "memory": result.memory,
                "audit_event": result.audit_event,
            }
        ),
    )
    store_idempotency_replay(
        session,
        idempotency,
        request_id=result.request_id,
        workflow_id=result.workflow_id,
        status=result.status,
        response_status_code=200,
        replay_payload=response.model_dump(mode="json"),
        related_ids=result.ids,
    )
    return response


def _memory_mutation_idempotency_context(
    body: MemoryArchiveRequestBody | MemoryEditRequestBody | MemoryReviewRequestBody,
    *,
    memory_id: str,
    workflow_type: str,
    header_idempotency_key: object | None,
) -> IdempotencyContext | None:
    idempotency_key = resolve_write_request_idempotency(
        header_idempotency_key=header_idempotency_key,
        body_idempotency_key=body.idempotency_key,
    )
    request_payload = body.model_dump(
        mode="json",
        exclude={"request_id", "idempotency_key"},
    )
    request_payload["memory_id"] = memory_id
    return build_idempotency_context(
        workflow_type=workflow_type,
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )


def _character_create_idempotency_context(
    request: CharacterCreateRequestBody,
    *,
    header_idempotency_key: object | None,
) -> IdempotencyContext | None:
    idempotency_key = resolve_write_request_idempotency(
        header_idempotency_key=header_idempotency_key,
        body_idempotency_key=request.idempotency_key,
    )
    return build_idempotency_context(
        workflow_type=CHARACTER_CREATE_WORKFLOW_TYPE,
        idempotency_key=idempotency_key,
        request_payload=request.model_dump(
            mode="json",
            exclude={"request_id", "idempotency_key"},
        ),
    )


def _character_create_error_response(
    error: Exception,
    *,
    correlation: CorrelationContext | None,
) -> JSONResponse:
    status_code = _character_create_status_code_for_error(error)
    error_correlation = (
        build_error_correlation(
            correlation,
            status=WorkflowStatus.FAILED,
            failed_step=CHARACTER_CREATE_WORKFLOW_TYPE,
        )
        if correlation is not None
        else None
    )
    envelope = build_error_envelope(
        _normalize_character_create_error(error),
        correlation=error_correlation,
    )
    return JSONResponse(
        status_code=status_code,
        content=redact_payload(envelope),
    )


def _character_create_status_code_for_error(error: Exception) -> int:
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, LookupError):
        return 404
    if isinstance(error, ValueError):
        return 422
    if isinstance(error, ValidationError):
        return 422
    return 500


def _normalize_character_create_error(error: Exception) -> NormalizedError:
    if not isinstance(error, ValidationError):
        return normalize_error(error)
    details = []
    for item in error.errors(include_input=False, include_context=False):
        details.append(
            {
                "loc": list(item.get("loc", [])),
                "msg": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
        )
    message = details[0]["msg"] if details else "Request validation failed"
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return NormalizedError(
        code="validation_error",
        message=message,
        details={"errors": details},
    )
