from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.application.inspection import (
    CharacterSummary,
    ClaimSummary,
    ContextPackageDetail,
    ConversationDetail,
    EvidenceRefSummary,
    ExpansionState,
    LayeredSummary,
    MemorySummary,
    MessageSummary,
    PersonaVersionSummary,
    SourceChunkDetail,
    SourceChunkSummary,
    UserSummary,
)
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ContextPackage,
    Conversation,
    EvidenceRef,
    Memory,
    Message,
    PersonaVersion,
    SourceChunk,
    User,
)
from personality_jelly.runtime import parse_layered_summary
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ConversationRepository,
    ContextPackageRepository,
    EvidenceRefRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    UserRepository,
)


@dataclass(frozen=True)
class ConversationInspectionOptions:
    message_limit: int = 10
    include_user: bool = True
    include_character: bool = True
    include_persona_version: bool = True
    include_memories: bool = False


@dataclass(frozen=True)
class ContextPackageInspectionOptions:
    include_persona_version: bool = False
    include_claims: bool = False
    include_evidence: bool = False
    include_evidence_chunks: bool = False
    include_memories: bool = False
    include_retrieved_chunks: bool = False
    include_retrieved_chunk_text: bool = False


def inspect_conversation(
    session: Session,
    conversation_id: str,
    *,
    options: ConversationInspectionOptions | None = None,
) -> ConversationDetail:
    active_options = options or ConversationInspectionOptions()
    if active_options.message_limit < 0:
        raise ValueError("message_limit must be 0 or greater")

    conversation = ConversationRepository(session).require(conversation_id)
    messages = MessageRepository(session).list_by_conversation(conversation.id)
    if active_options.message_limit:
        messages = messages[-active_options.message_limit :]
    else:
        messages = []

    user = (
        UserRepository(session).require(conversation.user_id)
        if active_options.include_user
        else None
    )
    character = (
        CharacterRepository(session).require(conversation.character_id)
        if active_options.include_character
        else None
    )
    persona = (
        PersonaVersionRepository(session).require(conversation.persona_version_id)
        if active_options.include_persona_version
        else None
    )
    memories = (
        MemoryRepository(session).list_for_user_character(
            conversation.user_id,
            conversation.character_id,
        )
        if active_options.include_memories
        else []
    )

    return ConversationDetail(
        **_conversation_fields(conversation),
        summary_layers=_layered_summary(conversation.summary),
        user=_user_summary(user) if user is not None else None,
        character=_character_summary(character) if character is not None else None,
        persona_version=_persona_version_summary(persona) if persona is not None else None,
        message_count=len(MessageRepository(session).list_by_conversation(conversation.id)),
        messages=[_message_summary(message) for message in messages],
        memories=[_memory_summary(memory) for memory in memories],
    )


def inspect_context_package(
    session: Session,
    context_package_id: str,
    *,
    options: ContextPackageInspectionOptions | None = None,
) -> ContextPackageDetail:
    active_options = options or ContextPackageInspectionOptions()
    context_package = ContextPackageRepository(session).require(context_package_id)
    expanded: list[str] = []

    persona = None
    if active_options.include_persona_version:
        persona = PersonaVersionRepository(session).require(context_package.persona_version_id)
        expanded.append("persona_version")

    evidence_repository = EvidenceRefRepository(session)
    source_chunk_repository = SourceChunkRepository(session)
    claims = []
    if active_options.include_claims:
        claim_repository = CanonClaimRepository(session)
        claims = [claim_repository.require(claim_id) for claim_id in context_package.claim_ids]
        expanded.append("claims")
        if active_options.include_evidence:
            expanded.append("evidence")
        if active_options.include_evidence_chunks:
            expanded.append("evidence_chunks")

    memories = []
    if active_options.include_memories:
        memory_repository = MemoryRepository(session)
        memories = [memory_repository.require(memory_id) for memory_id in context_package.memory_ids]
        expanded.append("memories")

    retrieved_chunks = []
    if active_options.include_retrieved_chunks:
        retrieved_chunks = [
            source_chunk_repository.require(chunk_id)
            for chunk_id in context_package.retrieved_chunk_ids
        ]
        expanded.append(
            "retrieved_chunk_details"
            if active_options.include_retrieved_chunk_text
            else "retrieved_chunks"
        )

    mode = "detail" if expanded else "ids"
    return ContextPackageDetail(
        **_context_package_fields(context_package),
        expansion=ExpansionState(mode=mode, expanded=expanded),
        assembled_prompt=context_package.assembled_prompt,
        persona_version=_persona_version_summary(persona) if persona is not None else None,
        claims=[
            _claim_summary(
                claim,
                evidence_repository=evidence_repository,
                source_chunk_repository=source_chunk_repository,
                include_evidence=active_options.include_evidence,
                include_evidence_chunks=active_options.include_evidence_chunks,
            )
            for claim in claims
        ],
        memories=[_memory_summary(memory) for memory in memories],
        retrieved_chunks=[
            _source_chunk_detail(chunk)
            if active_options.include_retrieved_chunk_text
            else _source_chunk_summary(chunk)
            for chunk in retrieved_chunks
        ],
    )


def _conversation_fields(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "user_id": conversation.user_id,
        "character_id": conversation.character_id,
        "persona_version_id": conversation.persona_version_id,
        "current_mode": conversation.current_mode,
        "summary": conversation.summary,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


def _context_package_fields(context_package: ContextPackage) -> dict:
    return {
        "id": context_package.id,
        "conversation_id": context_package.conversation_id,
        "interaction_mode": context_package.interaction_mode,
        "persona_version_id": context_package.persona_version_id,
        "claim_ids": context_package.claim_ids,
        "memory_ids": context_package.memory_ids,
        "retrieved_chunk_ids": context_package.retrieved_chunk_ids,
        "created_at": context_package.created_at,
    }


def _layered_summary(summary: str | None) -> LayeredSummary:
    layers = parse_layered_summary(summary)
    return LayeredSummary(
        short_term_scene_state=layers.short_term_scene_state,
        user_memory_candidates=layers.user_memory_candidates,
        relationship_memory_notes=layers.relationship_memory_notes,
        reflective_notes=layers.reflective_notes,
    )


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        display_name=user.display_name,
        created_at=user.created_at,
    )


def _character_summary(character: Character) -> CharacterSummary:
    return CharacterSummary(
        id=character.id,
        source_work_id=character.source_work_id,
        canonical_name=character.canonical_name,
        aliases=character.aliases,
        created_at=character.created_at,
    )


def _persona_version_summary(persona: PersonaVersion) -> PersonaVersionSummary:
    return PersonaVersionSummary(
        id=persona.id,
        character_id=persona.character_id,
        source_work_id=persona.source_work_id,
        version_number=persona.version_number,
        source_claim_ids=persona.source_claim_ids,
        created_at=persona.created_at,
        core_self=persona.core_self,
    )


def _message_summary(message: Message) -> MessageSummary:
    return MessageSummary(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        context_package_id=message.context_package_id,
        created_at=message.created_at,
    )


def _memory_summary(memory: Memory) -> MemorySummary:
    return MemorySummary(
        id=memory.id,
        user_id=memory.user_id,
        character_id=memory.character_id,
        conversation_id=memory.conversation_id,
        scope=memory.scope,
        status=memory.status,
        content=memory.content,
        importance=memory.importance,
        reason=memory.reason,
        created_at=memory.created_at,
    )


def _claim_summary(
    claim: CanonClaim,
    *,
    evidence_repository: EvidenceRefRepository,
    source_chunk_repository: SourceChunkRepository,
    include_evidence: bool,
    include_evidence_chunks: bool,
) -> ClaimSummary:
    evidence_refs = evidence_repository.list_by_claim(claim.id)
    return ClaimSummary(
        id=claim.id,
        source_work_id=claim.source_work_id,
        character_id=claim.character_id,
        claim_type=claim.claim_type,
        status=claim.status,
        confidence=claim.confidence,
        content=claim.content,
        reasoning=claim.reasoning,
        created_by=claim.created_by,
        evidence_ids=[evidence.id for evidence in evidence_refs],
        evidence=[
            _evidence_ref_summary(
                evidence,
                source_chunk_repository=source_chunk_repository,
                include_chunk=include_evidence_chunks,
            )
            for evidence in evidence_refs
        ]
        if include_evidence
        else [],
    )


def _evidence_ref_summary(
    evidence: EvidenceRef,
    *,
    source_chunk_repository: SourceChunkRepository,
    include_chunk: bool,
) -> EvidenceRefSummary:
    chunk = source_chunk_repository.require(evidence.chunk_id) if include_chunk else None
    return EvidenceRefSummary(
        id=evidence.id,
        claim_id=evidence.claim_id,
        chunk_id=evidence.chunk_id,
        excerpt=evidence.excerpt,
        support_score=evidence.support_score,
        chunk=_source_chunk_summary(chunk) if chunk is not None else None,
    )


def _source_chunk_summary(chunk: SourceChunk) -> SourceChunkSummary:
    return SourceChunkSummary(
        id=chunk.id,
        source_work_id=chunk.source_work_id,
        chapter_index=chunk.chapter_index,
        chapter_title=chunk.chapter_title,
        paragraph_index=chunk.paragraph_index,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text_preview=_text_preview(chunk.text),
    )


def _source_chunk_detail(chunk: SourceChunk) -> SourceChunkDetail:
    return SourceChunkDetail(
        id=chunk.id,
        source_work_id=chunk.source_work_id,
        chapter_index=chunk.chapter_index,
        chapter_title=chunk.chapter_title,
        paragraph_index=chunk.paragraph_index,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text_preview=_text_preview(chunk.text),
        text=chunk.text,
    )


def _text_preview(text: str, *, limit: int = 120) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 1].rstrip() + "..."
