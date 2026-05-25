from __future__ import annotations

"""Transport-neutral inspection result models.

Expansion convention:

- Summary models expose durable IDs and cheap scalar fields by default.
- Detail models add large text fields or linked child collections.
- Linked entities should default to IDs. Services may populate optional summary/detail fields when
  the caller asks for expansion, and record that choice in `ExpansionState`.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny
from sqlalchemy.orm import Session

from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    CriticAction,
    CriticRiskLevel,
    EvidenceRef,
    EvaluationCaseStatus,
    EvaluationStatus,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    MessageRole,
    PersonaVersion,
    SourceChunk,
    SourceWork,
)
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    EvidenceRefRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
)


class InspectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class LinkedId(InspectionModel):
    entity_type: str
    id: str


class ExpansionState(InspectionModel):
    mode: Literal["ids", "summary", "detail"] = "ids"
    expanded: list[str] = Field(default_factory=list)
    omitted: list[str] = Field(default_factory=list)


class SourceWorkSummary(InspectionModel):
    id: str
    title: str
    author: str | None = None
    language: str
    source_type: str
    created_at: datetime


class SourceChunkSummary(InspectionModel):
    id: str
    source_work_id: str
    chapter_index: int | None = None
    chapter_title: str | None = None
    paragraph_index: int
    char_start: int | None = None
    char_end: int | None = None
    text_preview: str | None = None


class SourceChunkDetail(SourceChunkSummary):
    text: str


class EvidenceRefSummary(InspectionModel):
    id: str
    claim_id: str
    chunk_id: str
    excerpt: str
    support_score: float = Field(ge=0.0, le=1.0)
    chunk: SourceChunkSummary | None = None


class ClaimSummary(InspectionModel):
    id: str
    source_work_id: str
    character_id: str
    claim_type: ClaimType
    status: ClaimStatus
    confidence: float = Field(ge=0.0, le=1.0)
    content: str
    reasoning: str | None = None
    created_by: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRefSummary] = Field(default_factory=list)


class PersonaVersionSummary(InspectionModel):
    id: str
    character_id: str
    source_work_id: str
    version_number: int = Field(ge=1)
    source_claim_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class CharacterSummary(InspectionModel):
    id: str
    source_work_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime
    latest_persona_version_id: str | None = None
    claim_count: int | None = Field(default=None, ge=0)
    evidence_count: int | None = Field(default=None, ge=0)


class CharacterDetail(CharacterSummary):
    source_work: SourceWorkSummary | None = None
    latest_persona_version: PersonaVersionSummary | None = None
    claims: list[ClaimSummary] = Field(default_factory=list)


class UserSummary(InspectionModel):
    id: str
    display_name: str | None = None
    created_at: datetime


class LayeredSummary(InspectionModel):
    short_term_scene_state: str
    user_memory_candidates: list[str] = Field(default_factory=list)
    relationship_memory_notes: list[str] = Field(default_factory=list)
    reflective_notes: list[str] = Field(default_factory=list)


class MessageSummary(InspectionModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    context_package_id: str | None = None
    created_at: datetime


class MemorySummary(InspectionModel):
    id: str
    user_id: str
    character_id: str
    conversation_id: str | None = None
    scope: MemoryScope
    status: MemoryStatus
    content: str
    importance: float = Field(ge=0.0, le=1.0)
    reason: str
    created_at: datetime


class ConversationSummary(InspectionModel):
    id: str
    user_id: str
    character_id: str
    persona_version_id: str
    current_mode: InteractionMode
    summary: str | None = None
    summary_layers: LayeredSummary | None = None
    created_at: datetime
    updated_at: datetime
    user: UserSummary | None = None
    character: CharacterSummary | None = None
    persona_version: PersonaVersionSummary | None = None


class ConversationDetail(ConversationSummary):
    messages: list[MessageSummary] = Field(default_factory=list)
    memories: list[MemorySummary] = Field(default_factory=list)
    failure_cases: list[FailureCaseSummary] = Field(default_factory=list)


class ContextPackageSummary(InspectionModel):
    id: str
    conversation_id: str
    interaction_mode: InteractionMode
    persona_version_id: str
    claim_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    expansion: ExpansionState = Field(default_factory=ExpansionState)


class ContextPackageDetail(ContextPackageSummary):
    assembled_prompt: str
    persona_version: PersonaVersionSummary | None = None
    claims: list[ClaimSummary] = Field(default_factory=list)
    memories: list[MemorySummary] = Field(default_factory=list)
    retrieved_chunks: list[SourceChunkSummary] = Field(default_factory=list)


class CriticReportSummary(InspectionModel):
    id: str
    message_id: str
    ooc_risk: CriticRiskLevel
    fact_risk: CriticRiskLevel
    memory_risk: CriticRiskLevel
    mode_risk: CriticRiskLevel
    suggested_action: CriticAction
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime


class CriticReportDetail(CriticReportSummary):
    message: MessageSummary | None = None


class FailureCaseSummary(InspectionModel):
    id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    context_package_id: str
    critic_report_id: str
    category: str
    reason: str
    notes: str | None = None
    created_at: datetime


class FailureCaseDetail(FailureCaseSummary):
    user_message: MessageSummary | None = None
    assistant_message: MessageSummary | None = None
    context_package: ContextPackageSummary | None = None
    critic_report: CriticReportSummary | None = None


class LLMTraceSummary(InspectionModel):
    id: str
    operation: str
    schema_name: str
    provider_name: str
    model_name: str | None = None
    validation_error_count: int = Field(ge=0)
    created_at: datetime


class LLMTraceDetail(LLMTraceSummary):
    raw_output: str
    response_schema: dict[str, Any] = Field(default_factory=dict)
    parsed_output: dict[str, Any] | None = None
    validation_errors: list[str] = Field(default_factory=list)


class BenchmarkModeDiagnostics(InspectionModel):
    interaction_mode: InteractionMode | str
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)


class OOCBenchmarkDiagnostics(InspectionModel):
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    mode_reports: list[BenchmarkModeDiagnostics] = Field(default_factory=list)


class RetrievalBenchmarkDiagnostics(InspectionModel):
    total_cases: int = Field(ge=0)
    evidence_case_count: int = Field(ge=0)
    empty_case_count: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    evidence_pass_rate: float = Field(ge=0.0, le=1.0)
    empty_pass_rate: float = Field(ge=0.0, le=1.0)
    average_recall: float = Field(ge=0.0, le=1.0)
    average_ranking_score: float = Field(ge=0.0, le=1.0)
    first_relevant_at_one_count: int = Field(ge=0)
    no_relevant_result_count: int = Field(ge=0)
    retrieved_empty_when_expected_empty_count: int = Field(ge=0)
    retrieved_nonempty_when_expected_empty_count: int = Field(ge=0)
    missing_expected_chunk_count: int = Field(ge=0)


class EvaluationCaseResultSummary(InspectionModel):
    id: str
    run_id: str
    case_id: str
    prompt: str
    interaction_mode: InteractionMode
    assistant_message_id: str
    critic_report_id: str | None = None
    status: EvaluationCaseStatus
    reasons: list[str] = Field(default_factory=list)
    category: str
    created_at: datetime


class EvaluationRunSummary(InspectionModel):
    id: str
    character_id: str
    persona_version_id: str
    test_suite: str
    status: EvaluationStatus
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    created_at: datetime
    completed_at: datetime | None = None
    diagnostics: OOCBenchmarkDiagnostics | None = None


class EvaluationRunDetail(EvaluationRunSummary):
    cases: list[EvaluationCaseResultSummary] = Field(default_factory=list)


class RetrievalEvaluationCaseResultSummary(InspectionModel):
    id: str
    run_id: str
    case_id: str
    query: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_scores: list[float | None] = Field(default_factory=list)
    status: EvaluationCaseStatus
    recall: float = Field(ge=0.0, le=1.0)
    first_relevant_rank: int | None = None
    ranking_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime


class RetrievalEvaluationRunSummary(InspectionModel):
    id: str
    source_work_id: str
    character_id: str
    test_suite: str
    status: EvaluationStatus
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    embedding_model: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    diagnostics: RetrievalBenchmarkDiagnostics | None = None


class RetrievalEvaluationRunDetail(RetrievalEvaluationRunSummary):
    cases: list[RetrievalEvaluationCaseResultSummary] = Field(default_factory=list)


class InspectionListResult(InspectionModel):
    items: list[SerializeAsAny[InspectionModel]]
    total_count: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=1)
    expansion: ExpansionState = Field(default_factory=ExpansionState)


def get_character_detail(
    session: Session,
    character_id: str,
    *,
    include_claims: bool = True,
    expand_claim_evidence: bool = True,
    expand_evidence_chunks: bool = False,
) -> CharacterDetail:
    character_repository = CharacterRepository(session)
    source_work_repository = SourceWorkRepository(session)
    persona_repository = PersonaVersionRepository(session)
    claim_repository = CanonClaimRepository(session)
    evidence_repository = EvidenceRefRepository(session)
    chunk_repository = SourceChunkRepository(session)

    character = character_repository.require(character_id)
    source_work = source_work_repository.require(character.source_work_id)
    latest_persona = persona_repository.latest_for_character(character.id)
    claims = claim_repository.list_by_character(character.id)
    evidence_by_claim = _evidence_by_claim(evidence_repository, claims)
    chunks_by_id = (
        _chunks_by_evidence(chunk_repository, _flatten_evidence(evidence_by_claim))
        if expand_evidence_chunks
        else {}
    )

    claim_summaries = (
        [
            _claim_to_summary(
                claim,
                evidence_refs=evidence_by_claim[claim.id],
                chunks_by_id=chunks_by_id,
                include_evidence=expand_claim_evidence,
            )
            for claim in claims
        ]
        if include_claims
        else []
    )

    return CharacterDetail(
        **_character_summary_payload(
            character,
            latest_persona=latest_persona,
            claim_count=len(claims),
            evidence_count=sum(len(evidence) for evidence in evidence_by_claim.values()),
        ),
        source_work=_source_work_to_summary(source_work),
        latest_persona_version=(
            _persona_version_to_summary(latest_persona) if latest_persona is not None else None
        ),
        claims=claim_summaries,
    )


def list_claims(
    session: Session,
    character_id: str,
    *,
    status: ClaimStatus | str | None = None,
    claim_type: ClaimType | str | None = None,
    expand_evidence: bool = True,
    expand_chunks: bool = False,
) -> InspectionListResult:
    CharacterRepository(session).require(character_id)
    claim_repository = CanonClaimRepository(session)
    evidence_repository = EvidenceRefRepository(session)
    chunk_repository = SourceChunkRepository(session)

    claims = claim_repository.list_by_character(
        character_id,
        status=_claim_status(status),
        claim_type=_claim_type(claim_type),
    )
    evidence_by_claim = _evidence_by_claim(evidence_repository, claims)
    chunks_by_id = (
        _chunks_by_evidence(chunk_repository, _flatten_evidence(evidence_by_claim))
        if expand_chunks
        else {}
    )
    items = [
        _claim_to_summary(
            claim,
            evidence_refs=evidence_by_claim[claim.id],
            chunks_by_id=chunks_by_id,
            include_evidence=expand_evidence,
        )
        for claim in claims
    ]

    return InspectionListResult(
        items=items,
        total_count=len(items),
        expansion=_claim_expansion_state(expand_evidence, expand_chunks),
    )


def get_claim_detail(
    session: Session,
    claim_id: str,
    *,
    expand_chunks: bool = True,
) -> ClaimSummary:
    claim = CanonClaimRepository(session).require(claim_id)
    evidence_refs = EvidenceRefRepository(session).list_by_claim(claim.id)
    chunks_by_id = (
        _chunks_by_evidence(SourceChunkRepository(session), evidence_refs) if expand_chunks else {}
    )
    return _claim_to_summary(claim, evidence_refs=evidence_refs, chunks_by_id=chunks_by_id)


def list_memories(
    session: Session,
    user_id: str,
    character_id: str,
    *,
    scope: MemoryScope | str | None = None,
    status: MemoryStatus | str | None = None,
) -> InspectionListResult:
    UserRepository(session).require(user_id)
    CharacterRepository(session).require(character_id)
    memories = MemoryRepository(session).list_for_user_character(
        user_id,
        character_id,
        scope=_memory_scope(scope),
        status=_memory_status(status),
    )

    return InspectionListResult(
        items=[_memory_to_summary(memory) for memory in memories],
        total_count=len(memories),
        expansion=ExpansionState(mode="summary"),
    )


def get_memory_detail(session: Session, memory_id: str) -> MemorySummary:
    memory = MemoryRepository(session).require(memory_id)
    return _memory_to_summary(memory)


def get_source_chunk_detail(session: Session, chunk_id: str) -> SourceChunkDetail:
    chunk = SourceChunkRepository(session).require(chunk_id)
    return _source_chunk_to_detail(chunk)


def _source_work_to_summary(source_work: SourceWork) -> SourceWorkSummary:
    return SourceWorkSummary(
        id=source_work.id,
        title=source_work.title,
        author=source_work.author,
        language=source_work.language,
        source_type=source_work.source_type,
        created_at=source_work.created_at,
    )


def _source_chunk_to_summary(
    chunk: SourceChunk,
    *,
    include_preview: bool = True,
) -> SourceChunkSummary:
    return SourceChunkSummary(
        id=chunk.id,
        source_work_id=chunk.source_work_id,
        chapter_index=chunk.chapter_index,
        chapter_title=chunk.chapter_title,
        paragraph_index=chunk.paragraph_index,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text_preview=_text_preview(chunk.text) if include_preview else None,
    )


def _source_chunk_to_detail(chunk: SourceChunk) -> SourceChunkDetail:
    return SourceChunkDetail(
        **_source_chunk_to_summary(chunk, include_preview=True).model_dump(),
        text=chunk.text,
    )


def _evidence_ref_to_summary(
    evidence_ref: EvidenceRef,
    *,
    chunk: SourceChunk | None = None,
) -> EvidenceRefSummary:
    return EvidenceRefSummary(
        id=evidence_ref.id,
        claim_id=evidence_ref.claim_id,
        chunk_id=evidence_ref.chunk_id,
        excerpt=evidence_ref.excerpt,
        support_score=evidence_ref.support_score,
        chunk=_source_chunk_to_summary(chunk) if chunk is not None else None,
    )


def _claim_to_summary(
    claim: CanonClaim,
    *,
    evidence_refs: list[EvidenceRef] | None = None,
    chunks_by_id: dict[str, SourceChunk] | None = None,
    include_evidence: bool = True,
) -> ClaimSummary:
    evidence_refs = evidence_refs or []
    chunks_by_id = chunks_by_id or {}
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
        evidence=(
            [
                _evidence_ref_to_summary(evidence, chunk=chunks_by_id.get(evidence.chunk_id))
                for evidence in evidence_refs
            ]
            if include_evidence
            else []
        ),
    )


def _persona_version_to_summary(persona_version: PersonaVersion) -> PersonaVersionSummary:
    return PersonaVersionSummary(
        id=persona_version.id,
        character_id=persona_version.character_id,
        source_work_id=persona_version.source_work_id,
        version_number=persona_version.version_number,
        source_claim_ids=persona_version.source_claim_ids,
        created_at=persona_version.created_at,
    )


def _character_summary_payload(
    character: Character,
    *,
    latest_persona: PersonaVersion | None = None,
    claim_count: int | None = None,
    evidence_count: int | None = None,
) -> dict[str, object]:
    return {
        "id": character.id,
        "source_work_id": character.source_work_id,
        "canonical_name": character.canonical_name,
        "aliases": character.aliases,
        "created_at": character.created_at,
        "latest_persona_version_id": latest_persona.id if latest_persona is not None else None,
        "claim_count": claim_count,
        "evidence_count": evidence_count,
    }


def _memory_to_summary(memory: Memory) -> MemorySummary:
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


def _evidence_by_claim(
    repository: EvidenceRefRepository,
    claims: list[CanonClaim],
) -> dict[str, list[EvidenceRef]]:
    return {claim.id: repository.list_by_claim(claim.id) for claim in claims}


def _flatten_evidence(evidence_by_claim: dict[str, list[EvidenceRef]]) -> list[EvidenceRef]:
    return [evidence for evidence_refs in evidence_by_claim.values() for evidence in evidence_refs]


def _chunks_by_evidence(
    repository: SourceChunkRepository,
    evidence_refs: list[EvidenceRef],
) -> dict[str, SourceChunk]:
    chunk_ids = {evidence.chunk_id for evidence in evidence_refs}
    return {chunk_id: repository.require(chunk_id) for chunk_id in chunk_ids}


def _text_preview(text: str, *, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _claim_status(status: ClaimStatus | str | None) -> ClaimStatus | None:
    return ClaimStatus(status) if status is not None else None


def _claim_type(claim_type: ClaimType | str | None) -> ClaimType | None:
    return ClaimType(claim_type) if claim_type is not None else None


def _memory_scope(scope: MemoryScope | str | None) -> MemoryScope | None:
    return MemoryScope(scope) if scope is not None else None


def _memory_status(status: MemoryStatus | str | None) -> MemoryStatus | None:
    return MemoryStatus(status) if status is not None else None


def _claim_expansion_state(expand_evidence: bool, expand_chunks: bool) -> ExpansionState:
    if not expand_evidence:
        return ExpansionState(mode="ids", omitted=["evidence"])
    if expand_chunks:
        return ExpansionState(mode="detail", expanded=["evidence", "evidence.chunk"])
    return ExpansionState(mode="summary", expanded=["evidence"], omitted=["evidence.chunk"])
