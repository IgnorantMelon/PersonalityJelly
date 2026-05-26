from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session
from personality_jelly.api.errors import build_error_envelope
from personality_jelly.api.redaction import redact_payload
from personality_jelly.api.schemas import (
    REQUEST_ID_HEADER,
    ConversationCreateRequest,
    ConversationCreateResponse,
    resolve_write_request_correlation,
)
from personality_jelly.application import (
    CONVERSATION_CREATE_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    ContextPackageDetail,
    ContextPackageInspectionOptions,
    ConversationDetail,
    ConversationInspectionOptions,
    InspectionListResult,
    WorkflowStatus,
    build_error_correlation,
    create_conversation_workflow,
    inspect_context_package,
    inspect_conversation,
    list_conversations,
    normalize_error,
)

router = APIRouter(tags=["conversation-context"])


@router.post(
    "/conversations",
    response_model=ConversationCreateResponse,
    status_code=201,
)
def post_conversation(
    request: ConversationCreateRequest,
    session: Annotated[Session, Depends(get_session)],
    header_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
) -> ConversationCreateResponse | JSONResponse:
    correlation: CorrelationContext | None = None
    try:
        write_correlation = resolve_write_request_correlation(
            header_request_id=header_request_id,
            body_request_id=request.request_id,
        )
        correlation = write_correlation.to_application_context()
        result = create_conversation_workflow(
            session,
            user_id=request.user_id,
            character_id=request.character_id,
            persona_version_id=request.persona_version_id,
            conversation_id=request.conversation_id,
            interaction_mode=request.interaction_mode,
            actor_context=request.actor.to_application_context(),
            correlation_context=correlation,
        )
    except Exception as error:
        return _conversation_create_error_response(error, correlation=correlation)

    response = ConversationCreateResponse.from_application_result(
        result,
        audit_event=result.audit_event.model_dump(mode="json"),
    )
    return ConversationCreateResponse.model_validate(redact_payload(response))


@router.get("/conversations", response_model=InspectionListResult)
def get_conversations(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> InspectionListResult:
    return list_conversations(session, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    session: Annotated[Session, Depends(get_session)],
    message_limit: Annotated[int, Query(ge=0)] = 10,
    include_user: bool = True,
    include_character: bool = True,
    include_persona_version: bool = True,
    include_memories: bool = False,
) -> ConversationDetail:
    return inspect_conversation(
        session,
        conversation_id,
        options=ConversationInspectionOptions(
            message_limit=message_limit,
            include_user=include_user,
            include_character=include_character,
            include_persona_version=include_persona_version,
            include_memories=include_memories,
        ),
    )


@router.get("/context-packages/{context_package_id}", response_model=ContextPackageDetail)
def get_context_package(
    context_package_id: str,
    session: Annotated[Session, Depends(get_session)],
    include_persona_version: bool = False,
    include_claims: bool = False,
    include_evidence: bool = False,
    include_evidence_chunks: bool = False,
    include_memories: bool = False,
    include_retrieved_chunks: bool = False,
    include_retrieved_chunk_text: bool = False,
) -> ContextPackageDetail:
    return inspect_context_package(
        session,
        context_package_id,
        options=ContextPackageInspectionOptions(
            include_persona_version=include_persona_version,
            include_claims=include_claims,
            include_evidence=include_evidence,
            include_evidence_chunks=include_evidence_chunks,
            include_memories=include_memories,
            include_retrieved_chunks=include_retrieved_chunks,
            include_retrieved_chunk_text=include_retrieved_chunk_text,
        ),
    )


def _conversation_create_error_response(
    error: Exception,
    *,
    correlation: CorrelationContext | None,
) -> JSONResponse:
    status_code = _status_code_for_error(error)
    error_correlation = (
        build_error_correlation(
            correlation,
            status=WorkflowStatus.FAILED,
            failed_step=CONVERSATION_CREATE_WORKFLOW_TYPE,
        )
        if correlation is not None
        else None
    )
    envelope = build_error_envelope(
        normalize_error(error),
        correlation=error_correlation,
    )
    return JSONResponse(
        status_code=status_code,
        content=redact_payload(envelope),
    )


def _status_code_for_error(error: Exception) -> int:
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, LookupError):
        return 404
    if isinstance(error, ValueError):
        return 422
    return 500
