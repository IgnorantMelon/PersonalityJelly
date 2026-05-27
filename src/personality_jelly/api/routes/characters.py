from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from personality_jelly.api.character_schemas import (
    CharacterCreateRequestBody,
    CharacterCreateResponse,
)
from personality_jelly.api.dependencies import get_session, get_write_session
from personality_jelly.api.errors import build_error_envelope
from personality_jelly.api.memory_mutation_schemas import (
    MemoryArchiveRequestBody,
    MemoryEditRequestBody,
    MemoryReviewRequestBody,
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
    CHARACTER_CREATE_SUCCESS_STATUS_CODE,
    CHARACTER_CREATE_WORKFLOW_TYPE,
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
    NormalizedError,
    SourceChunkDetail,
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
    review_memory_workflow,
    store_idempotency_replay,
)
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryScope, MemoryStatus

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
