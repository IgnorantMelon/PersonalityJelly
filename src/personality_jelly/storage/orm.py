from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceWorkORM(Base):
    __tablename__ = "source_works"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    chunks: Mapped[list[SourceChunkORM]] = relationship(back_populates="source_work")
    characters: Mapped[list[CharacterORM]] = relationship(back_populates="source_work")


class SourceChunkORM(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        Index(
            "ix_source_chunks_work_chapter_paragraph",
            "source_work_id",
            "chapter_index",
            "paragraph_index",
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    source_work_id: Mapped[str] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    chapter_index: Mapped[int | None] = mapped_column(Integer)
    chapter_title: Mapped[str | None] = mapped_column(String(255))
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)

    source_work: Mapped[SourceWorkORM] = relationship(back_populates="chunks")


class CharacterORM(Base):
    __tablename__ = "characters"
    __table_args__ = (Index("ix_characters_work_name", "source_work_id", "canonical_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_work_id: Mapped[str] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_work: Mapped[SourceWorkORM] = relationship(back_populates="characters")


class CanonClaimORM(Base):
    __tablename__ = "canon_claims"
    __table_args__ = (
        Index(
            "ix_canon_claims_character_type_status",
            "character_id",
            "claim_type",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    source_work_id: Mapped[str] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


class EvidenceRefORM(Base):
    __tablename__ = "evidence_refs"
    __table_args__ = (Index("ix_evidence_refs_claim_chunk", "claim_id", "chunk_id"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("canon_claims.id"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("source_chunks.id"), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    support_score: Mapped[float] = mapped_column(Float, nullable=False)


class ClaimConflictORM(Base):
    __tablename__ = "claim_conflicts"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    claim_a_id: Mapped[str] = mapped_column(ForeignKey("canon_claims.id"), nullable=False)
    claim_b_id: Mapped[str] = mapped_column(ForeignKey("canon_claims.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text)


class PersonaVersionORM(Base):
    __tablename__ = "persona_versions"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    source_work_id: Mapped[str] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    core_self: Mapped[str] = mapped_column(Text, nullable=False)
    speech_rules: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    behavior_rules: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    world_adaptation_rules: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    forbidden_rules: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    source_claim_ids: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversationORM(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_character", "user_id", "character_id"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    persona_version_id: Mapped[str] = mapped_column(ForeignKey("persona_versions.id"), nullable=False)
    current_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageORM(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_package_id: Mapped[str | None] = mapped_column(String(96))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MemoryORM(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index(
            "ix_memories_user_character_scope_status",
            "user_id",
            "character_id",
            "scope",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContextPackageORM(Base):
    __tablename__ = "context_packages"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    interaction_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    persona_version_id: Mapped[str] = mapped_column(ForeignKey("persona_versions.id"), nullable=False)
    claim_ids: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    memory_ids: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    assembled_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CriticReportORM(Base):
    __tablename__ = "critic_reports"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    ooc_risk: Mapped[str] = mapped_column(String(32), nullable=False)
    fact_risk: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_risk: Mapped[str] = mapped_column(String(32), nullable=False)
    mode_risk: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    suggested_action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FailureCaseORM(Base):
    __tablename__ = "failure_cases"
    __table_args__ = (
        Index("ix_failure_cases_conversation_created", "conversation_id", "created_at"),
        Index("ix_failure_cases_category_created", "category", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    assistant_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    context_package_id: Mapped[str] = mapped_column(
        ForeignKey("context_packages.id"),
        nullable=False,
    )
    critic_report_id: Mapped[str] = mapped_column(ForeignKey("critic_reports.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationRunORM(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index(
            "ix_evaluation_runs_character_persona",
            "character_id",
            "persona_version_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    persona_version_id: Mapped[str] = mapped_column(ForeignKey("persona_versions.id"), nullable=False)
    test_suite: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationCaseResultORM(Base):
    __tablename__ = "evaluation_case_results"
    __table_args__ = (Index("ix_evaluation_case_results_run", "run_id"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    interaction_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    assistant_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    critic_report_id: Mapped[str | None] = mapped_column(ForeignKey("critic_reports.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def create_all(bind) -> None:
    Base.metadata.create_all(bind=bind)
