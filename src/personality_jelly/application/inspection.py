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

from personality_jelly.domain import (
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
    chunk: SerializeAsAny[SourceChunkSummary] | None = None


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
    retrieved_chunks: list[SerializeAsAny[SourceChunkSummary]] = Field(default_factory=list)


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
