from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session
from personality_jelly.application import (
    ContextPackageDetail,
    ContextPackageInspectionOptions,
    ConversationDetail,
    ConversationInspectionOptions,
    InspectionListResult,
    inspect_context_package,
    inspect_conversation,
    list_conversations,
)

router = APIRouter(tags=["conversation-context"])


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
