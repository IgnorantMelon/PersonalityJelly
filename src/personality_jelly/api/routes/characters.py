from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session
from personality_jelly.application import (
    CharacterDetail,
    ClaimSummary,
    InspectionListResult,
    MemorySummary,
    SourceChunkDetail,
    get_character_detail,
    get_claim_detail,
    get_memory_detail,
    get_source_chunk_detail,
    list_characters,
    list_claims,
    list_memories,
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


@router.get("/source-chunks/{chunk_id}", response_model=SourceChunkDetail)
def get_source_chunk(
    chunk_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> SourceChunkDetail:
    return get_source_chunk_detail(session, chunk_id)
