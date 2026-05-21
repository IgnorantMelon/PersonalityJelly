from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain.enums import (
    ClaimStatus,
    ClaimType,
    CriticAction,
    CriticRiskLevel,
    EvaluationCaseStatus,
    EvaluationStatus,
    InteractionMode,
    MemoryScope,
    MemoryStatus,
    MessageRole,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        use_enum_values=True,
    )


class SourceWork(DomainModel):
    id: str
    title: str
    author: str | None = None
    language: str = "zh-CN"
    source_type: str
    created_at: datetime = Field(default_factory=utc_now)


class SourceChunk(DomainModel):
    id: str
    source_work_id: str
    chapter_index: int | None = None
    chapter_title: str | None = None
    paragraph_index: int
    text: str
    char_start: int | None = None
    char_end: int | None = None


class SourceChunkEmbedding(DomainModel):
    id: str
    source_chunk_id: str
    embedding_model: str
    embedding: list[float]
    created_at: datetime = Field(default_factory=utc_now)


class Character(DomainModel):
    id: str
    source_work_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class CanonClaim(DomainModel):
    id: str
    source_work_id: str
    character_id: str
    claim_type: ClaimType
    content: str
    status: ClaimStatus = ClaimStatus.CANDIDATE
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    created_by: str


class EvidenceRef(DomainModel):
    id: str
    claim_id: str
    chunk_id: str
    excerpt: str
    support_score: float = Field(ge=0.0, le=1.0)


class ClaimConflict(DomainModel):
    id: str
    claim_a_id: str
    claim_b_id: str
    description: str
    resolution: str | None = None


class PersonaVersion(DomainModel):
    id: str
    character_id: str
    source_work_id: str
    version_number: int = Field(ge=1)
    core_self: str
    speech_rules: list[str] = Field(default_factory=list)
    behavior_rules: list[str] = Field(default_factory=list)
    world_adaptation_rules: list[str] = Field(default_factory=list)
    forbidden_rules: list[str] = Field(default_factory=list)
    source_claim_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class User(DomainModel):
    id: str
    display_name: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Conversation(DomainModel):
    id: str
    user_id: str
    character_id: str
    persona_version_id: str
    current_mode: InteractionMode = InteractionMode.REALITY_CHAT
    summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Message(DomainModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    context_package_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Memory(DomainModel):
    id: str
    user_id: str
    character_id: str
    conversation_id: str | None = None
    scope: MemoryScope
    status: MemoryStatus = MemoryStatus.CANDIDATE
    content: str
    importance: float = Field(ge=0.0, le=1.0)
    reason: str
    created_at: datetime = Field(default_factory=utc_now)


class ContextPackage(DomainModel):
    id: str
    conversation_id: str
    interaction_mode: InteractionMode
    persona_version_id: str
    claim_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    assembled_prompt: str
    created_at: datetime = Field(default_factory=utc_now)


class CriticReport(DomainModel):
    id: str
    message_id: str
    ooc_risk: CriticRiskLevel
    fact_risk: CriticRiskLevel
    memory_risk: CriticRiskLevel
    mode_risk: CriticRiskLevel
    reasons: list[str] = Field(default_factory=list)
    suggested_action: CriticAction
    created_at: datetime = Field(default_factory=utc_now)


class FailureCase(DomainModel):
    id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    context_package_id: str
    critic_report_id: str
    category: str
    reason: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class LLMRawOutput(DomainModel):
    id: str
    operation: str
    schema_name: str
    model_name: str | None = None
    provider_name: str
    raw_output: str
    response_schema: dict[str, Any] = Field(default_factory=dict)
    parsed_output: dict[str, Any] | None = None
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class EvaluationRun(DomainModel):
    id: str
    character_id: str
    persona_version_id: str
    test_suite: str
    status: EvaluationStatus = EvaluationStatus.RUNNING
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class EvaluationCaseResult(DomainModel):
    id: str
    run_id: str
    case_id: str
    prompt: str
    interaction_mode: InteractionMode
    assistant_message_id: str
    critic_report_id: str | None = None
    status: EvaluationCaseStatus
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class RetrievalEvaluationRun(DomainModel):
    id: str
    source_work_id: str
    character_id: str
    test_suite: str
    status: EvaluationStatus = EvaluationStatus.RUNNING
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    embedding_model: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class RetrievalEvaluationCaseResult(DomainModel):
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
    created_at: datetime = Field(default_factory=utc_now)

