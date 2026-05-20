from __future__ import annotations

from typing import TypeVar

from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimConflict,
    ContextPackage,
    Conversation,
    CriticReport,
    EvidenceRef,
    EvaluationCaseResult,
    EvaluationRun,
    Memory,
    Message,
    PersonaVersion,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.storage import orm


DomainT = TypeVar(
    "DomainT",
    SourceWork,
    SourceChunk,
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
    EvaluationRun,
    EvaluationCaseResult,
)


def source_work_to_orm(model: SourceWork) -> orm.SourceWorkORM:
    return orm.SourceWorkORM(**model.model_dump())


def source_work_from_orm(row: orm.SourceWorkORM) -> SourceWork:
    return SourceWork.model_validate(_column_dict(row))


def source_chunk_to_orm(model: SourceChunk) -> orm.SourceChunkORM:
    return orm.SourceChunkORM(**model.model_dump())


def source_chunk_from_orm(row: orm.SourceChunkORM) -> SourceChunk:
    return SourceChunk.model_validate(_column_dict(row))


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


def evaluation_run_to_orm(model: EvaluationRun) -> orm.EvaluationRunORM:
    return orm.EvaluationRunORM(**model.model_dump())


def evaluation_run_from_orm(row: orm.EvaluationRunORM) -> EvaluationRun:
    return EvaluationRun.model_validate(_column_dict(row))


def evaluation_case_result_to_orm(
    model: EvaluationCaseResult,
) -> orm.EvaluationCaseResultORM:
    return orm.EvaluationCaseResultORM(**model.model_dump())


def evaluation_case_result_from_orm(
    row: orm.EvaluationCaseResultORM,
) -> EvaluationCaseResult:
    return EvaluationCaseResult.model_validate(_column_dict(row))


def _column_dict(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}

