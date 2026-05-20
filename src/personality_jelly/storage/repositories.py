from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimConflict,
    ClaimStatus,
    ClaimType,
    ContextPackage,
    Conversation,
    CriticReport,
    EvidenceRef,
    EvaluationCaseResult,
    EvaluationCaseStatus,
    EvaluationRun,
    EvaluationStatus,
    FailureCase,
    Memory,
    MemoryScope,
    MemoryStatus,
    Message,
    PersonaVersion,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.storage import mappers
from personality_jelly.storage import orm


ModelT = TypeVar("ModelT")
OrmT = TypeVar("OrmT")


class Repository(Generic[ModelT, OrmT]):
    orm_model: type[OrmT]

    def __init__(
        self,
        session: Session,
        orm_model: type[OrmT],
        to_orm: Callable[[ModelT], OrmT],
        from_orm: Callable[[OrmT], ModelT],
    ) -> None:
        self.session = session
        self.orm_model = orm_model
        self._to_orm = to_orm
        self._from_orm = from_orm

    def add(self, model: ModelT) -> ModelT:
        self.session.add(self._to_orm(model))
        self.session.flush()
        return model

    def get(self, model_id: str) -> ModelT | None:
        row = self.session.get(self.orm_model, model_id)
        return self._from_orm(row) if row is not None else None

    def require(self, model_id: str) -> ModelT:
        row = self.get(model_id)
        if row is None:
            raise LookupError(f"{self.orm_model.__name__} {model_id!r} was not found")
        return row

    def list_all(self) -> list[ModelT]:
        return self._all(select(self.orm_model))

    def _all(self, statement: Select) -> list[ModelT]:
        return [self._from_orm(row) for row in self.session.scalars(statement).all()]


class SourceWorkRepository(Repository[SourceWork, orm.SourceWorkORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.SourceWorkORM,
            mappers.source_work_to_orm,
            mappers.source_work_from_orm,
        )

    def find_by_title(self, title: str) -> SourceWork | None:
        statement = (
            select(orm.SourceWorkORM)
            .where(orm.SourceWorkORM.title == title)
            .order_by(orm.SourceWorkORM.created_at.desc())
            .limit(1)
        )
        row = self.session.scalars(statement).first()
        return mappers.source_work_from_orm(row) if row is not None else None


class SourceChunkRepository(Repository[SourceChunk, orm.SourceChunkORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.SourceChunkORM,
            mappers.source_chunk_to_orm,
            mappers.source_chunk_from_orm,
        )

    def add_many(self, chunks: list[SourceChunk]) -> list[SourceChunk]:
        self.session.add_all(mappers.source_chunk_to_orm(chunk) for chunk in chunks)
        self.session.flush()
        return chunks

    def list_by_source_work(self, source_work_id: str) -> list[SourceChunk]:
        statement = (
            select(orm.SourceChunkORM)
            .where(orm.SourceChunkORM.source_work_id == source_work_id)
            .order_by(
                orm.SourceChunkORM.chapter_index.asc().nullsfirst(),
                orm.SourceChunkORM.paragraph_index.asc(),
                orm.SourceChunkORM.char_start.asc().nullsfirst(),
            )
        )
        return self._all(statement)


class CharacterRepository(Repository[Character, orm.CharacterORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.CharacterORM,
            mappers.character_to_orm,
            mappers.character_from_orm,
        )

    def list_by_source_work(self, source_work_id: str) -> list[Character]:
        statement = select(orm.CharacterORM).where(orm.CharacterORM.source_work_id == source_work_id)
        return self._all(statement)

    def find_by_source_work_and_name(
        self,
        source_work_id: str,
        canonical_name: str,
    ) -> Character | None:
        statement = (
            select(orm.CharacterORM)
            .where(
                orm.CharacterORM.source_work_id == source_work_id,
                orm.CharacterORM.canonical_name == canonical_name,
            )
            .order_by(orm.CharacterORM.created_at.desc())
            .limit(1)
        )
        row = self.session.scalars(statement).first()
        return mappers.character_from_orm(row) if row is not None else None


class CanonClaimRepository(Repository[CanonClaim, orm.CanonClaimORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.CanonClaimORM,
            mappers.canon_claim_to_orm,
            mappers.canon_claim_from_orm,
        )

    def list_by_character(
        self,
        character_id: str,
        status: ClaimStatus | None = None,
        claim_type: ClaimType | None = None,
    ) -> list[CanonClaim]:
        statement = select(orm.CanonClaimORM).where(orm.CanonClaimORM.character_id == character_id)
        if status is not None:
            statement = statement.where(orm.CanonClaimORM.status == status.value)
        if claim_type is not None:
            statement = statement.where(orm.CanonClaimORM.claim_type == claim_type.value)
        return self._all(statement)

    def update_status(
        self,
        claim_id: str,
        *,
        status: ClaimStatus | str,
        reasoning: str | None = None,
        confidence: float | None = None,
    ) -> CanonClaim:
        row = self.session.get(orm.CanonClaimORM, claim_id)
        if row is None:
            raise LookupError(f"CanonClaimORM {claim_id!r} was not found")
        row.status = status.value if isinstance(status, ClaimStatus) else status
        if reasoning is not None:
            row.reasoning = reasoning
        if confidence is not None:
            row.confidence = confidence
        self.session.flush()
        return mappers.canon_claim_from_orm(row)


class EvidenceRefRepository(Repository[EvidenceRef, orm.EvidenceRefORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.EvidenceRefORM,
            mappers.evidence_ref_to_orm,
            mappers.evidence_ref_from_orm,
        )

    def list_by_claim(self, claim_id: str) -> list[EvidenceRef]:
        statement = select(orm.EvidenceRefORM).where(orm.EvidenceRefORM.claim_id == claim_id)
        return self._all(statement)

    def add_many(self, evidence_refs: list[EvidenceRef]) -> list[EvidenceRef]:
        self.session.add_all(mappers.evidence_ref_to_orm(evidence) for evidence in evidence_refs)
        self.session.flush()
        return evidence_refs


class ClaimConflictRepository(Repository[ClaimConflict, orm.ClaimConflictORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.ClaimConflictORM,
            mappers.claim_conflict_to_orm,
            mappers.claim_conflict_from_orm,
        )

    def list_by_claim(self, claim_id: str) -> list[ClaimConflict]:
        statement = select(orm.ClaimConflictORM).where(
            (orm.ClaimConflictORM.claim_a_id == claim_id)
            | (orm.ClaimConflictORM.claim_b_id == claim_id)
        )
        return self._all(statement)


class PersonaVersionRepository(Repository[PersonaVersion, orm.PersonaVersionORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.PersonaVersionORM,
            mappers.persona_version_to_orm,
            mappers.persona_version_from_orm,
        )

    def latest_for_character(self, character_id: str) -> PersonaVersion | None:
        statement = (
            select(orm.PersonaVersionORM)
            .where(orm.PersonaVersionORM.character_id == character_id)
            .order_by(orm.PersonaVersionORM.version_number.desc())
            .limit(1)
        )
        row = self.session.scalars(statement).first()
        return mappers.persona_version_from_orm(row) if row is not None else None

    def next_version_number(self, character_id: str) -> int:
        latest = self.latest_for_character(character_id)
        return 1 if latest is None else latest.version_number + 1


class UserRepository(Repository[User, orm.UserORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, orm.UserORM, mappers.user_to_orm, mappers.user_from_orm)

    def find_by_display_name(self, display_name: str) -> User | None:
        statement = (
            select(orm.UserORM)
            .where(orm.UserORM.display_name == display_name)
            .order_by(orm.UserORM.created_at.desc())
            .limit(1)
        )
        row = self.session.scalars(statement).first()
        return mappers.user_from_orm(row) if row is not None else None


class ConversationRepository(Repository[Conversation, orm.ConversationORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.ConversationORM,
            mappers.conversation_to_orm,
            mappers.conversation_from_orm,
        )

    def list_for_user_character(self, user_id: str, character_id: str) -> list[Conversation]:
        statement = select(orm.ConversationORM).where(
            orm.ConversationORM.user_id == user_id,
            orm.ConversationORM.character_id == character_id,
        )
        return self._all(statement)

    def list_recent(self, limit: int | None = None) -> list[Conversation]:
        statement = select(orm.ConversationORM).order_by(orm.ConversationORM.updated_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return self._all(statement)

    def latest_for_user_character(
        self,
        user_id: str,
        character_id: str,
    ) -> Conversation | None:
        statement = (
            select(orm.ConversationORM)
            .where(
                orm.ConversationORM.user_id == user_id,
                orm.ConversationORM.character_id == character_id,
            )
            .order_by(orm.ConversationORM.updated_at.desc())
            .limit(1)
        )
        row = self.session.scalars(statement).first()
        return mappers.conversation_from_orm(row) if row is not None else None

    def update_summary(self, conversation_id: str, *, summary: str, updated_at) -> Conversation:
        row = self.session.get(orm.ConversationORM, conversation_id)
        if row is None:
            raise LookupError(f"ConversationORM {conversation_id!r} was not found")
        row.summary = summary
        row.updated_at = updated_at
        self.session.flush()
        return mappers.conversation_from_orm(row)


class MessageRepository(Repository[Message, orm.MessageORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.MessageORM,
            mappers.message_to_orm,
            mappers.message_from_orm,
        )

    def list_by_conversation(self, conversation_id: str) -> list[Message]:
        statement = (
            select(orm.MessageORM)
            .where(orm.MessageORM.conversation_id == conversation_id)
            .order_by(orm.MessageORM.created_at.asc())
        )
        return self._all(statement)


class MemoryRepository(Repository[Memory, orm.MemoryORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, orm.MemoryORM, mappers.memory_to_orm, mappers.memory_from_orm)

    def list_for_user_character(
        self,
        user_id: str,
        character_id: str,
        scope: MemoryScope | None = None,
        status: MemoryStatus | None = None,
    ) -> list[Memory]:
        statement = select(orm.MemoryORM).where(
            orm.MemoryORM.user_id == user_id,
            orm.MemoryORM.character_id == character_id,
        )
        if scope is not None:
            statement = statement.where(orm.MemoryORM.scope == scope.value)
        if status is not None:
            statement = statement.where(orm.MemoryORM.status == status.value)
        return self._all(statement)

    def update_status(self, memory_id: str, *, status: MemoryStatus | str) -> Memory:
        row = self.session.get(orm.MemoryORM, memory_id)
        if row is None:
            raise LookupError(f"MemoryORM {memory_id!r} was not found")
        row.status = status.value if isinstance(status, MemoryStatus) else status
        self.session.flush()
        return mappers.memory_from_orm(row)

    def update_content(self, memory_id: str, *, content: str, reason: str | None = None) -> Memory:
        row = self.session.get(orm.MemoryORM, memory_id)
        if row is None:
            raise LookupError(f"MemoryORM {memory_id!r} was not found")
        row.content = content
        if reason is not None:
            row.reason = reason
        self.session.flush()
        return mappers.memory_from_orm(row)


class ContextPackageRepository(Repository[ContextPackage, orm.ContextPackageORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.ContextPackageORM,
            mappers.context_package_to_orm,
            mappers.context_package_from_orm,
        )


class CriticReportRepository(Repository[CriticReport, orm.CriticReportORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.CriticReportORM,
            mappers.critic_report_to_orm,
            mappers.critic_report_from_orm,
        )


class FailureCaseRepository(Repository[FailureCase, orm.FailureCaseORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.FailureCaseORM,
            mappers.failure_case_to_orm,
            mappers.failure_case_from_orm,
        )

    def list_recent(
        self,
        *,
        limit: int | None = None,
        category: str | None = None,
    ) -> list[FailureCase]:
        statement = select(orm.FailureCaseORM).order_by(orm.FailureCaseORM.created_at.desc())
        if category is not None:
            statement = statement.where(orm.FailureCaseORM.category == category)
        if limit is not None:
            statement = statement.limit(limit)
        return self._all(statement)

    def list_by_conversation(self, conversation_id: str) -> list[FailureCase]:
        statement = (
            select(orm.FailureCaseORM)
            .where(orm.FailureCaseORM.conversation_id == conversation_id)
            .order_by(orm.FailureCaseORM.created_at.desc())
        )
        return self._all(statement)


class EvaluationRunRepository(Repository[EvaluationRun, orm.EvaluationRunORM]):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.EvaluationRunORM,
            mappers.evaluation_run_to_orm,
            mappers.evaluation_run_from_orm,
        )

    def list_recent(
        self,
        limit: int | None = None,
        *,
        character_id: str | None = None,
        test_suite: str | None = None,
    ) -> list[EvaluationRun]:
        statement = select(orm.EvaluationRunORM).order_by(orm.EvaluationRunORM.created_at.desc())
        if character_id is not None:
            statement = statement.where(orm.EvaluationRunORM.character_id == character_id)
        if test_suite is not None:
            statement = statement.where(orm.EvaluationRunORM.test_suite == test_suite)
        if limit is not None:
            statement = statement.limit(limit)
        return self._all(statement)

    def update_summary(
        self,
        run_id: str,
        *,
        status: EvaluationStatus,
        passed_cases: int,
        failed_cases: int,
        completed_at,
    ) -> EvaluationRun:
        row = self.session.get(orm.EvaluationRunORM, run_id)
        if row is None:
            raise LookupError(f"EvaluationRunORM {run_id!r} was not found")
        row.status = status.value
        row.passed_cases = passed_cases
        row.failed_cases = failed_cases
        row.completed_at = completed_at
        self.session.flush()
        return mappers.evaluation_run_from_orm(row)


class EvaluationCaseResultRepository(
    Repository[EvaluationCaseResult, orm.EvaluationCaseResultORM],
):
    def __init__(self, session: Session) -> None:
        super().__init__(
            session,
            orm.EvaluationCaseResultORM,
            mappers.evaluation_case_result_to_orm,
            mappers.evaluation_case_result_from_orm,
        )

    def list_by_run(self, run_id: str) -> list[EvaluationCaseResult]:
        statement = (
            select(orm.EvaluationCaseResultORM)
            .where(orm.EvaluationCaseResultORM.run_id == run_id)
            .order_by(orm.EvaluationCaseResultORM.created_at.asc())
        )
        return self._all(statement)

    def count_by_status(self, run_id: str, status: EvaluationCaseStatus) -> int:
        statement = select(orm.EvaluationCaseResultORM).where(
            orm.EvaluationCaseResultORM.run_id == run_id,
            orm.EvaluationCaseResultORM.status == status.value,
        )
        return len(self.session.scalars(statement).all())

