from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Literal

from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from personality_jelly.application.audit import (
    AuditEntity,
    AuditEventPayload,
    AuditRelatedIds as AuditPayloadRelatedIds,
    AuditResult,
    LocalActorContext,
    build_audit_metadata,
    persist_audit_event,
    require_local_actor_context,
)
from personality_jelly.application.correlation import (
    CorrelationContext,
    WorkflowLinkSpec,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    complete_persisted_workflow,
    start_persisted_workflow,
)
from personality_jelly.application.errors import ConflictError
from personality_jelly.application.idempotency import (
    IdempotencyContext,
    store_idempotency_replay,
)
from personality_jelly.application.inspection import InspectionModel, SourceWorkSummary
from personality_jelly.domain import SourceChunk, SourceWork
from personality_jelly.ingestion import ChunkingConfig, LoadedSource, ingest_loaded_source
from personality_jelly.storage import SourceWorkRepository


SOURCE_WORK_INGEST_WORKFLOW_TYPE = "source_work.ingest"
SOURCE_WORK_INGEST_AUDIT_REASON = "local API source ingest requested"
SOURCE_WORK_INGEST_SUCCESS_STATUS_CODE = 201
MAX_INLINE_SOURCE_CONTENT_CHARS = 200_000
MIN_CHUNK_MAX_PARAGRAPH_CHARS = 100
MAX_CHUNK_MAX_PARAGRAPH_CHARS = 10_000
MIN_CHUNK_MIN_PARAGRAPH_CHARS = 1
MAX_CHUNK_MIN_PARAGRAPH_CHARS = 1_000
MAX_CLIENT_METADATA_KEYS = 50
MAX_CLIENT_METADATA_DEPTH = 5
MAX_CLIENT_METADATA_STRING_LENGTH = 500

_ACCEPTED_SOURCE_TYPES = {"markdown", "txt"}
_ACCEPTED_CONTENT_ENCODINGS = {None, "utf-8"}
_FORBIDDEN_REQUEST_FIELDS = {
    "path",
    "file_path",
    "local_path",
    "source_path",
    "uri",
    "url",
    "remote_url",
    "file",
    "filename",
    "upload",
    "multipart",
    "base64",
    "binary",
    "provider",
    "provider_config",
    "prompt",
    "secret",
    "api_key",
}
_FORBIDDEN_METADATA_KEYS = {
    "path",
    "file_path",
    "local_path",
    "source_path",
    "uri",
    "url",
    "remote_url",
    "file",
    "filename",
    "upload",
    "multipart",
    "base64",
    "binary",
    "provider",
    "provider_config",
    "provider_settings",
    "llm_config",
    "embedding_config",
    "prompt",
    "raw_prompt",
    "system_message",
    "source_text",
    "chunk_text",
    "full_text",
    "secret",
    "secrets",
    "api_key",
    "token",
    "password",
}
_WINDOWS_PATH_PATTERN = re.compile(r"^[a-zA-Z]:[\\/].+")
_POSIX_PATH_PATTERN = re.compile(
    r"^/(?:Users|home|var|tmp|etc|opt|mnt|Volumes|private|data|root|workspace|projects)/.+"
)
_URL_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_BASE64_HINT_PATTERN = re.compile(
    r"^(?:data:[^;]+;base64,|[A-Za-z0-9+/]{80,}={0,2}$)",
    re.IGNORECASE,
)


class SourceWorkIngestChunking(InspectionModel):
    max_paragraph_chars: int = ChunkingConfig.max_paragraph_chars
    min_paragraph_chars: int = ChunkingConfig.min_paragraph_chars

    @field_validator("max_paragraph_chars")
    @classmethod
    def _validate_max_paragraph_chars(cls, value: int) -> int:
        if not MIN_CHUNK_MAX_PARAGRAPH_CHARS <= value <= MAX_CHUNK_MAX_PARAGRAPH_CHARS:
            raise ValueError(
                "chunking.max_paragraph_chars must be between "
                f"{MIN_CHUNK_MAX_PARAGRAPH_CHARS} and {MAX_CHUNK_MAX_PARAGRAPH_CHARS}"
            )
        return value

    @field_validator("min_paragraph_chars")
    @classmethod
    def _validate_min_paragraph_chars(cls, value: int) -> int:
        if not MIN_CHUNK_MIN_PARAGRAPH_CHARS <= value <= MAX_CHUNK_MIN_PARAGRAPH_CHARS:
            raise ValueError(
                "chunking.min_paragraph_chars must be between "
                f"{MIN_CHUNK_MIN_PARAGRAPH_CHARS} and {MAX_CHUNK_MIN_PARAGRAPH_CHARS}"
            )
        return value

    def to_chunking_config(self) -> ChunkingConfig:
        if self.min_paragraph_chars > self.max_paragraph_chars:
            raise ValueError(
                "chunking.min_paragraph_chars must not exceed chunking.max_paragraph_chars"
            )
        return ChunkingConfig(
            max_paragraph_chars=self.max_paragraph_chars,
            min_paragraph_chars=self.min_paragraph_chars,
        )


class SourceWorkIngestRequest(InspectionModel):
    source_work_id: str | None = Field(default=None, min_length=1, max_length=128)
    title: str = Field(min_length=1)
    author: str | None = None
    language: str = "zh-CN"
    source_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    content_encoding: str | None = None
    chunking: SourceWorkIngestChunking = Field(default_factory=SourceWorkIngestChunking)
    actor: LocalActorContext | None
    correlation: CorrelationContext
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_work_id", "title", "author", "language", "source_type")
    @classmethod
    def _normalize_text_field(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("source ingest text fields must not be blank")
        return normalized

    @field_validator("source_work_id")
    @classmethod
    def _validate_source_work_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _reject_forbidden_text(value, field_path="source_work_id")
        return value

    @field_validator("source_type")
    @classmethod
    def _validate_source_type(cls, value: str) -> str:
        if value not in _ACCEPTED_SOURCE_TYPES:
            raise ValueError("source_type must be markdown or txt")
        return value

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        if len(value) > MAX_INLINE_SOURCE_CONTENT_CHARS:
            raise ValueError(
                f"content must be at most {MAX_INLINE_SOURCE_CONTENT_CHARS} characters"
            )
        _reject_forbidden_text(value, field_path="content")
        return value

    @field_validator("content_encoding")
    @classmethod
    def _validate_content_encoding(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in _ACCEPTED_CONTENT_ENCODINGS:
            raise ValueError("content_encoding must be omitted or utf-8")
        return normalized

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_safe_metadata(value, field_path="metadata")


class SourceWorkIngestReplay(InspectionModel):
    response_status_code: int = SOURCE_WORK_INGEST_SUCCESS_STATUS_CODE
    replay_payload: dict[str, Any]


class SourceWorkIngestResult(WorkflowResponseSummary):
    workflow_type: Literal["source_work.ingest"] = SOURCE_WORK_INGEST_WORKFLOW_TYPE
    status: WorkflowStatus | str = WorkflowStatus.COMPLETED
    source_work: SourceWorkSummary
    chunk_count: int
    source_chunk_ids: list[str]
    first_chunk_id: str | None = None
    last_chunk_id: str | None = None
    text_redacted: bool = True
    source_preview_redacted: bool = True
    llm_trace_ids: list[str] = Field(default_factory=list)
    audit_event: AuditEventPayload


def ingest_source_work_workflow(
    session: Session,
    request: SourceWorkIngestRequest,
    *,
    idempotency: IdempotencyContext | None = None,
    replay: SourceWorkIngestReplay | None = None,
) -> SourceWorkIngestResult:
    actor = require_local_actor_context(request.actor)
    _validate_safe_metadata(actor.metadata, field_path="actor.metadata")
    chunking_config = request.chunking.to_chunking_config()
    loaded_source = LoadedSource(
        title=request.title,
        source_type=request.source_type,
        text=request.content,
        path=None,
    )

    preview_chunks = _chunk_source_without_persisting(
        loaded_source=loaded_source,
        source_work_id=request.source_work_id,
        chunking_config=chunking_config,
    )
    if not preview_chunks:
        raise ValueError("content produced zero source chunks")

    with _source_ingest_transaction(session):
        if request.source_work_id is not None:
            existing = SourceWorkRepository(session).get(request.source_work_id)
            if existing is not None:
                raise ConflictError(
                    f"SourceWork {request.source_work_id!r} already exists",
                    details={"source_work_id": request.source_work_id},
                )

        workflow = start_persisted_workflow(
            session,
            request.correlation,
            workflow_type=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
            related_ids=WorkflowRelatedIds(source_work_id=request.source_work_id),
        )
        ingestion = ingest_loaded_source(
            session,
            loaded_source,
            source_work_id=request.source_work_id,
            author=request.author,
            language=request.language,
            chunking_config=chunking_config,
        )
        if not ingestion.chunks:
            raise ValueError("content produced zero source chunks")

        ids = _related_ids(ingestion.source_work, ingestion.chunks)
        completed_workflow = workflow.model_copy(
            update={
                "status": WorkflowStatus.COMPLETED,
                "related_ids": ids,
            }
        )
        audit_event = _build_source_ingest_audit_event(
            source_work=ingestion.source_work,
            chunks=ingestion.chunks,
            actor_context=actor,
            workflow=completed_workflow,
            metadata=request.metadata,
        )
        persist_audit_event(session, audit_event)
        ids = _related_ids(
            ingestion.source_work,
            ingestion.chunks,
            audit_event=audit_event,
        )
        workflow = complete_persisted_workflow(
            session,
            workflow,
            ids=ids,
            links=_source_ingest_links(
                ingestion.source_work,
                ingestion.chunks,
                audit_event=audit_event,
            ),
        )
        result = _build_result(
            workflow=workflow,
            ids=ids,
            source_work=ingestion.source_work,
            chunks=ingestion.chunks,
            audit_event=audit_event,
        )
        idempotency_record = store_idempotency_replay(
            session,
            idempotency,
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            status=str(result.status),
            response_status_code=(
                replay.response_status_code
                if replay is not None
                else SOURCE_WORK_INGEST_SUCCESS_STATUS_CODE
            ),
            replay_payload=(
                replay.replay_payload
                if replay is not None
                else _default_replay_payload(result)
            ),
            related_ids={
                **ids.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                "source_chunk_ids": result.source_chunk_ids,
            },
        )
        if idempotency_record is not None:
            complete_persisted_workflow(
                session,
                workflow,
                ids=ids,
                links=[
                    WorkflowLinkSpec(
                        entity_type="idempotency_record",
                        entity_id=idempotency_record.id,
                        relation="idempotency",
                    )
                ],
            )

    return result


def _chunk_source_without_persisting(
    *,
    loaded_source: LoadedSource,
    source_work_id: str | None,
    chunking_config: ChunkingConfig,
) -> list[SourceChunk]:
    from personality_jelly.core import EntityKind, generate_id
    from personality_jelly.ingestion.chunker import chunk_source_text

    return chunk_source_text(
        source_work_id=source_work_id or generate_id(EntityKind.SOURCE_WORK),
        text=loaded_source.text,
        config=chunking_config,
    )


@contextmanager
def _source_ingest_transaction(session: Session):
    if session.in_transaction():
        with session.begin_nested():
            yield
        return

    with session.begin():
        yield


def _build_source_ingest_audit_event(
    *,
    source_work: SourceWork,
    chunks: list[SourceChunk],
    actor_context: LocalActorContext,
    workflow,
    metadata: dict[str, Any],
) -> AuditEventPayload:
    source_metadata = _source_work_summary(source_work).model_dump(mode="json")
    chunk_ids = [chunk.id for chunk in chunks]
    after = {
        "source_work": source_metadata,
        "chunk_count": len(chunks),
        "first_chunk_id": chunk_ids[0] if chunk_ids else None,
        "last_chunk_id": chunk_ids[-1] if chunk_ids else None,
        "text_redacted": True,
        "source_preview_redacted": True,
    }
    return AuditEventPayload(
        actor=actor_context.to_audit_actor(),
        operation=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
        entity=AuditEntity(entity_type="source_work", entity_id=source_work.id),
        related_ids=AuditPayloadRelatedIds(source_work_id=source_work.id),
        reason=actor_context.operation_reason or SOURCE_WORK_INGEST_AUDIT_REASON,
        before=None,
        after=after,
        metadata=build_audit_metadata(
            {
                "workflow": SOURCE_WORK_INGEST_WORKFLOW_TYPE,
                "source_type": source_work.source_type,
                "language": source_work.language,
                "chunk_count": len(chunks),
                "first_chunk_id": chunk_ids[0] if chunk_ids else None,
                "last_chunk_id": chunk_ids[-1] if chunk_ids else None,
                "source_chunk_ids": chunk_ids,
                "client_metadata": metadata,
                "text_redacted": True,
                "source_preview_redacted": True,
            },
            actor_context=actor_context,
            correlation=workflow,
            result=AuditResult.SUCCEEDED,
        ),
    )


def _related_ids(
    source_work: SourceWork,
    chunks: list[SourceChunk],
    *,
    audit_event: AuditEventPayload | None = None,
) -> WorkflowRelatedIds:
    return WorkflowRelatedIds(
        source_work_id=source_work.id,
        audit_event_id=audit_event.id if audit_event is not None else None,
        audit_event_ids=[audit_event.id] if audit_event is not None else [],
        llm_trace_ids=[],
    )


def _source_ingest_links(
    source_work: SourceWork,
    chunks: list[SourceChunk],
    *,
    audit_event: AuditEventPayload,
) -> list[WorkflowLinkSpec]:
    links = [
        WorkflowLinkSpec(
            entity_type="source_work",
            entity_id=source_work.id,
            relation="created",
        )
    ]
    links.extend(
        WorkflowLinkSpec(entity_type="source_chunk", entity_id=chunk.id, relation="created")
        for chunk in chunks
    )
    links.append(
        WorkflowLinkSpec(
            entity_type="audit_event",
            entity_id=audit_event.id,
            relation="audit",
        )
    )
    return links


def _build_result(
    *,
    workflow,
    ids: WorkflowRelatedIds,
    source_work: SourceWork,
    chunks: list[SourceChunk],
    audit_event: AuditEventPayload,
) -> SourceWorkIngestResult:
    chunk_ids = [chunk.id for chunk in chunks]
    return SourceWorkIngestResult(
        request_id=workflow.request_id,
        workflow_id=workflow.workflow_id,
        workflow_type=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
        status=WorkflowStatus.COMPLETED,
        ids=ids,
        warnings=[],
        source_work=_source_work_summary(source_work),
        chunk_count=len(chunks),
        source_chunk_ids=chunk_ids,
        first_chunk_id=chunk_ids[0] if chunk_ids else None,
        last_chunk_id=chunk_ids[-1] if chunk_ids else None,
        text_redacted=True,
        source_preview_redacted=True,
        llm_trace_ids=[],
        audit_event=audit_event,
    )


def _source_work_summary(source_work: SourceWork) -> SourceWorkSummary:
    return SourceWorkSummary.model_validate(source_work.model_dump(mode="python"))


def _default_replay_payload(result: SourceWorkIngestResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type,
        "status": result.status,
        "ids": result.ids.model_dump(mode="json"),
        "result": {
            "source_work": result.source_work.model_dump(mode="json"),
            "persisted_ids": {"source_chunk_ids": result.source_chunk_ids},
            "chunk_count": result.chunk_count,
            "chunk_ids": result.source_chunk_ids,
            "first_chunk_id": result.first_chunk_id,
            "last_chunk_id": result.last_chunk_id,
            "text_redacted": True,
            "source_preview_redacted": True,
        },
        "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
    }


def _validate_safe_metadata(
    value: dict[str, Any],
    *,
    field_path: str,
    depth: int = 0,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_path} must be an object")
    if depth > MAX_CLIENT_METADATA_DEPTH:
        raise ValueError(f"{field_path} exceeds maximum nesting depth")
    if len(value) > MAX_CLIENT_METADATA_KEYS:
        raise ValueError(f"{field_path} has too many keys")

    validated: dict[str, Any] = {}
    for key, field_value in value.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError(f"{field_path} keys must not be blank")
        if _normalize_key(normalized_key) in _FORBIDDEN_METADATA_KEYS:
            raise ValueError(f"{field_path} contains forbidden source reference fields")
        _reject_forbidden_text(normalized_key, field_path=f"{field_path} key")
        validated[normalized_key] = _validate_metadata_value(
            field_value,
            field_path=f"{field_path}.{normalized_key}",
            depth=depth + 1,
        )
    return validated


def _validate_metadata_value(value: Any, *, field_path: str, depth: int) -> Any:
    if isinstance(value, dict):
        return _validate_safe_metadata(value, field_path=field_path, depth=depth)
    if isinstance(value, list | tuple):
        if len(value) > MAX_CLIENT_METADATA_KEYS:
            raise ValueError(f"{field_path} has too many values")
        return [
            _validate_metadata_value(item, field_path=field_path, depth=depth + 1)
            for item in value
        ]
    if isinstance(value, str):
        if len(value) > MAX_CLIENT_METADATA_STRING_LENGTH:
            raise ValueError(f"{field_path} must be bounded metadata")
        _reject_forbidden_text(value, field_path=field_path)
    return value


def _reject_forbidden_text(value: str, *, field_path: str) -> None:
    lowered = value.strip().lower()
    if lowered in _FORBIDDEN_REQUEST_FIELDS:
        raise ValueError(f"{field_path} contains forbidden source reference fields")
    if _WINDOWS_PATH_PATTERN.match(value) or _POSIX_PATH_PATTERN.match(value):
        raise ValueError(f"{field_path} must not contain local paths")
    if _URL_PATTERN.match(value):
        raise ValueError(f"{field_path} must not contain URLs")
    if _BASE64_HINT_PATTERN.match(value.strip()):
        raise ValueError(f"{field_path} must not contain binary or base64 payloads")


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")
