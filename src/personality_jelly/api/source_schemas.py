from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from personality_jelly.api.schemas import WriteRequestIdBody, WriteResponseEnvelope
from personality_jelly.application import (
    AuditActorType,
    CorrelationContext,
    LocalActorContext,
    SourceWorkIngestChunking,
    SourceWorkIngestRequest,
    SourceWorkIngestResult as ApplicationSourceWorkIngestResult,
)
from personality_jelly.application.correlation import MAX_CORRELATION_ID_LENGTH
from personality_jelly.application.inspection import InspectionModel, SourceWorkSummary


class SourceWorkIngestActor(InspectionModel):
    actor_type: AuditActorType = AuditActorType.API_USER
    actor_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    actor_label: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    user_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    operation_reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_context(self) -> LocalActorContext:
        return LocalActorContext(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            actor_label=self.actor_label,
            user_id=self.user_id,
            operation_reason=self.operation_reason,
            metadata=self.metadata,
        )


class SourceWorkIngestRequestBody(WriteRequestIdBody):
    source_work_id: str | None = Field(default=None, min_length=1, max_length=128)
    title: str = Field(min_length=1)
    author: str | None = Field(default=None, max_length=500)
    language: str = Field(default="zh-CN", min_length=1, max_length=64)
    source_type: Literal["markdown", "txt"]
    content: str = Field(min_length=1)
    content_encoding: Literal["utf-8"] | None = None
    chunking: SourceWorkIngestChunking = Field(default_factory=SourceWorkIngestChunking)
    actor: SourceWorkIngestActor
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_request(
        self,
        correlation: CorrelationContext,
    ) -> SourceWorkIngestRequest:
        return SourceWorkIngestRequest(
            source_work_id=self.source_work_id,
            title=self.title,
            author=self.author,
            language=self.language,
            source_type=self.source_type,
            content=self.content,
            content_encoding=self.content_encoding,
            chunking=self.chunking,
            actor=self.actor.to_application_context(),
            correlation=correlation,
            metadata=self.metadata,
        )


class SourceWorkIngestPersistedIds(InspectionModel):
    source_chunk_ids: list[str] = Field(default_factory=list)


class SourceWorkIngestResponseResult(InspectionModel):
    source_work: SourceWorkSummary
    persisted_ids: SourceWorkIngestPersistedIds
    chunk_count: int
    chunk_ids: list[str] = Field(default_factory=list)
    first_chunk_id: str | None = None
    last_chunk_id: str | None = None
    text_redacted: bool = True
    source_preview_redacted: bool = True


class SourceWorkIngestResponse(WriteResponseEnvelope):
    result: SourceWorkIngestResponseResult

    @classmethod
    def from_application_result(
        cls,
        result: ApplicationSourceWorkIngestResult,
    ) -> "SourceWorkIngestResponse":
        return cls(
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            workflow_type=result.workflow_type,
            status=result.status,
            ids=result.ids,
            warnings=result.warnings,
            result=SourceWorkIngestResponseResult(
                source_work=result.source_work,
                persisted_ids=SourceWorkIngestPersistedIds(
                    source_chunk_ids=result.source_chunk_ids,
                ),
                chunk_count=result.chunk_count,
                chunk_ids=result.source_chunk_ids,
                first_chunk_id=result.first_chunk_id,
                last_chunk_id=result.last_chunk_id,
                text_redacted=True,
                source_preview_redacted=True,
            ),
        )
