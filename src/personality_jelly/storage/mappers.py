from __future__ import annotations

from typing import TypeVar

from personality_jelly.domain import (
    AuditEvent,
    CanonClaim,
    Character,
    ClaimConflict,
    ContextPackage,
    Conversation,
    CriticReport,
    EvidenceRef,
    EvaluationCaseResult,
    EvaluationRun,
    FailureCase,
    LLMRawOutput,
    Memory,
    Message,
    PersonaVersion,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRun,
    SourceChunk,
    SourceChunkEmbedding,
    SourceWork,
    User,
)
from personality_jelly.storage import orm


_EVALUATION_CASE_CATEGORY_META_PREFIX = "__pjelly_case_category__:"


DomainT = TypeVar(
    "DomainT",
    SourceWork,
    SourceChunk,
    SourceChunkEmbedding,
    Character,
    CanonClaim,
    EvidenceRef,
    ClaimConflict,
    PersonaVersion,
    User,
    Conversation,
    Message,
    Memory,
    ContextPackage,
    CriticReport,
    FailureCase,
    LLMRawOutput,
    EvaluationRun,
    EvaluationCaseResult,
    RetrievalEvaluationRun,
    RetrievalEvaluationCaseResult,
    AuditEvent,
)


def source_work_to_orm(model: SourceWork) -> orm.SourceWorkORM:
    return orm.SourceWorkORM(**model.model_dump())


def source_work_from_orm(row: orm.SourceWorkORM) -> SourceWork:
    return SourceWork.model_validate(_column_dict(row))


def source_chunk_to_orm(model: SourceChunk) -> orm.SourceChunkORM:
    return orm.SourceChunkORM(**model.model_dump())


def source_chunk_from_orm(row: orm.SourceChunkORM) -> SourceChunk:
    return SourceChunk.model_validate(_column_dict(row))


def source_chunk_embedding_to_orm(model: SourceChunkEmbedding) -> orm.SourceChunkEmbeddingORM:
    return orm.SourceChunkEmbeddingORM(**model.model_dump())


def source_chunk_embedding_from_orm(
    row: orm.SourceChunkEmbeddingORM,
) -> SourceChunkEmbedding:
    return SourceChunkEmbedding.model_validate(_column_dict(row))


def character_to_orm(model: Character) -> orm.CharacterORM:
    return orm.CharacterORM(**model.model_dump())


def character_from_orm(row: orm.CharacterORM) -> Character:
    return Character.model_validate(_column_dict(row))


def canon_claim_to_orm(model: CanonClaim) -> orm.CanonClaimORM:
    return orm.CanonClaimORM(**model.model_dump())


def canon_claim_from_orm(row: orm.CanonClaimORM) -> CanonClaim:
    return CanonClaim.model_validate(_column_dict(row))


def evidence_ref_to_orm(model: EvidenceRef) -> orm.EvidenceRefORM:
    return orm.EvidenceRefORM(**model.model_dump())


def evidence_ref_from_orm(row: orm.EvidenceRefORM) -> EvidenceRef:
    return EvidenceRef.model_validate(_column_dict(row))


def claim_conflict_to_orm(model: ClaimConflict) -> orm.ClaimConflictORM:
    return orm.ClaimConflictORM(**model.model_dump())


def claim_conflict_from_orm(row: orm.ClaimConflictORM) -> ClaimConflict:
    return ClaimConflict.model_validate(_column_dict(row))


def persona_version_to_orm(model: PersonaVersion) -> orm.PersonaVersionORM:
    return orm.PersonaVersionORM(**model.model_dump())


def persona_version_from_orm(row: orm.PersonaVersionORM) -> PersonaVersion:
    return PersonaVersion.model_validate(_column_dict(row))


def user_to_orm(model: User) -> orm.UserORM:
    return orm.UserORM(**model.model_dump())


def user_from_orm(row: orm.UserORM) -> User:
    return User.model_validate(_column_dict(row))


def conversation_to_orm(model: Conversation) -> orm.ConversationORM:
    return orm.ConversationORM(**model.model_dump())


def conversation_from_orm(row: orm.ConversationORM) -> Conversation:
    return Conversation.model_validate(_column_dict(row))


def message_to_orm(model: Message) -> orm.MessageORM:
    return orm.MessageORM(**model.model_dump())


def message_from_orm(row: orm.MessageORM) -> Message:
    return Message.model_validate(_column_dict(row))


def memory_to_orm(model: Memory) -> orm.MemoryORM:
    return orm.MemoryORM(**model.model_dump())


def memory_from_orm(row: orm.MemoryORM) -> Memory:
    return Memory.model_validate(_column_dict(row))


def context_package_to_orm(model: ContextPackage) -> orm.ContextPackageORM:
    return orm.ContextPackageORM(**model.model_dump())


def context_package_from_orm(row: orm.ContextPackageORM) -> ContextPackage:
    return ContextPackage.model_validate(_column_dict(row))


def critic_report_to_orm(model: CriticReport) -> orm.CriticReportORM:
    return orm.CriticReportORM(**model.model_dump())


def critic_report_from_orm(row: orm.CriticReportORM) -> CriticReport:
    return CriticReport.model_validate(_column_dict(row))


def failure_case_to_orm(model: FailureCase) -> orm.FailureCaseORM:
    return orm.FailureCaseORM(**model.model_dump())


def failure_case_from_orm(row: orm.FailureCaseORM) -> FailureCase:
    return FailureCase.model_validate(_column_dict(row))


def llm_raw_output_to_orm(model: LLMRawOutput) -> orm.LLMRawOutputORM:
    return orm.LLMRawOutputORM(**model.model_dump())


def llm_raw_output_from_orm(row: orm.LLMRawOutputORM) -> LLMRawOutput:
    return LLMRawOutput.model_validate(_column_dict(row))


def audit_event_to_orm(model: AuditEvent) -> orm.AuditEventORM:
    payload = model.model_dump(mode="python")
    metadata = payload.pop("metadata")
    return orm.AuditEventORM(**payload, metadata_json=metadata)


def audit_event_from_orm(row: orm.AuditEventORM) -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "id": row.id,
            "created_at": row.created_at,
            "operation": row.operation,
            "result": row.result,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "reason": row.reason,
            "request_id": row.request_id,
            "workflow_id": row.workflow_id,
            "workflow_type": row.workflow_type,
            "user_id": row.user_id,
            "character_id": row.character_id,
            "conversation_id": row.conversation_id,
            "memory_id": row.memory_id,
            "llm_trace_id": row.llm_trace_id,
            "evaluation_run_id": row.evaluation_run_id,
            "retrieval_evaluation_run_id": row.retrieval_evaluation_run_id,
            "related_ids": row.related_ids,
            "before": row.before,
            "after": row.after,
            "metadata": row.metadata_json,
            "persistence": row.persistence,
            "schema_version": row.schema_version,
        }
    )


def evaluation_run_to_orm(model: EvaluationRun) -> orm.EvaluationRunORM:
    return orm.EvaluationRunORM(**model.model_dump())


def evaluation_run_from_orm(row: orm.EvaluationRunORM) -> EvaluationRun:
    return EvaluationRun.model_validate(_column_dict(row))


def evaluation_case_result_to_orm(
    model: EvaluationCaseResult,
) -> orm.EvaluationCaseResultORM:
    payload = model.model_dump()
    category = payload.pop("category")
    reasons = list(payload["reasons"])
    reasons.append(f"{_EVALUATION_CASE_CATEGORY_META_PREFIX}{category}")
    payload["reasons"] = reasons
    return orm.EvaluationCaseResultORM(**payload)


def evaluation_case_result_from_orm(
    row: orm.EvaluationCaseResultORM,
) -> EvaluationCaseResult:
    payload = _column_dict(row)
    reasons: list[str] = []
    category = "ooc"
    for reason in payload["reasons"]:
        if (
            isinstance(reason, str)
            and reason.startswith(_EVALUATION_CASE_CATEGORY_META_PREFIX)
        ):
            category = reason.removeprefix(_EVALUATION_CASE_CATEGORY_META_PREFIX)
            continue
        reasons.append(reason)
    payload["reasons"] = reasons
    payload["category"] = category
    return EvaluationCaseResult.model_validate(payload)


def retrieval_evaluation_run_to_orm(
    model: RetrievalEvaluationRun,
) -> orm.RetrievalEvaluationRunORM:
    return orm.RetrievalEvaluationRunORM(**model.model_dump())


def retrieval_evaluation_run_from_orm(
    row: orm.RetrievalEvaluationRunORM,
) -> RetrievalEvaluationRun:
    return RetrievalEvaluationRun.model_validate(_column_dict(row))


def retrieval_evaluation_case_result_to_orm(
    model: RetrievalEvaluationCaseResult,
) -> orm.RetrievalEvaluationCaseResultORM:
    return orm.RetrievalEvaluationCaseResultORM(**model.model_dump())


def retrieval_evaluation_case_result_from_orm(
    row: orm.RetrievalEvaluationCaseResultORM,
) -> RetrievalEvaluationCaseResult:
    return RetrievalEvaluationCaseResult.model_validate(_column_dict(row))


def _column_dict(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}

