from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session, get_write_session
from personality_jelly.api.memory_mutation_schemas import (
    MemoryArchiveRequestBody,
    MemoryEditRequestBody,
    MemoryReviewRequestBody,
)
from personality_jelly.api.redaction import redact_payload
from personality_jelly.api.schemas import (
    REQUEST_ID_HEADER,
    WriteResponseEnvelope,
    resolve_write_request_correlation,
)
from personality_jelly.application import (
    CharacterDetail,
    ClaimSummary,
    InspectionListResult,
    ManualMemoryArchiveRequest,
    ManualMemoryEditRequest,
    ManualMemoryMutationResult,
    ManualMemoryReviewRequest,
    MemorySummary,
    SourceChunkDetail,
    archive_memory_workflow,
    edit_memory_workflow,
    get_character_detail,
    get_claim_detail,
    get_memory_detail,
    get_source_chunk_detail,
    list_characters,
    list_claims,
    list_memories,
    review_memory_workflow,
)
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryScope, MemoryStatus

router = APIRouter(tags=["characters"])


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
) -> WriteResponseEnvelope:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
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
    return _memory_mutation_response(result)


@router.patch("/memories/{memory_id}", response_model=WriteResponseEnvelope)
def edit_memory(
    memory_id: str,
    body: MemoryEditRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
) -> WriteResponseEnvelope:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
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
    return _memory_mutation_response(result)


@router.post("/memories/{memory_id}/archive", response_model=WriteResponseEnvelope)
def archive_memory(
    memory_id: str,
    body: MemoryArchiveRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
) -> WriteResponseEnvelope:
    correlation = resolve_write_request_correlation(
        header_request_id=x_request_id,
        body_request_id=body.request_id,
    ).to_application_context()
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
    return _memory_mutation_response(result)


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
    result: ManualMemoryMutationResult,
) -> WriteResponseEnvelope:
    return WriteResponseEnvelope(
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
