from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from personality_jelly.application.correlation import CorrelationContext, WorkflowContext
from personality_jelly.application.inspection import InspectionModel, MemorySummary
from personality_jelly.domain import Memory
from personality_jelly.domain.models import utc_now


BATCH_04_AUDIT_PERSISTENCE_DECISION: Literal["payload_only"] = "payload_only"


class AuditActorType(StrEnum):
    SYSTEM = "system"
    CLI_USER = "cli_user"
    API_USER = "api_user"
    PROVIDER = "provider"
    WORKSPACE_MEMBER = "workspace_member"


class AuditOperation(StrEnum):
    MEMORY_REVIEW = "memory.review"
    MEMORY_EDIT = "memory.edit"
    MEMORY_ARCHIVE = "memory.archive"
    CANON_CLAIM_REVIEW = "canon_claim.review"
    CONVERSATION_TURN = "conversation.turn"
    BENCHMARK_REVIEW = "benchmark.review"


class AuditResult(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    REJECTED = "rejected"
    RETRIED = "retried"


class AuditActor(InspectionModel):
    actor_type: AuditActorType
    actor_id: str = Field(min_length=1)

    @field_validator("actor_id", mode="before")
    @classmethod
    def _normalize_actor_id(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="actor_id")


class LocalActorContext(InspectionModel):
    """Local attribution context for write services, not an auth/account principal."""

    actor_type: AuditActorType
    actor_id: str = Field(min_length=1)
    actor_label: str | None = None
    user_id: str | None = None
    operation_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("actor_id", mode="before")
    @classmethod
    def _normalize_actor_id(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="actor_id")

    @field_validator("actor_label", "user_id", "operation_reason", mode="before")
    @classmethod
    def _normalize_optional_text_field(cls, value: object) -> object:
        return _normalize_optional_text(value, field_name="local actor field")

    @field_validator("metadata", mode="before")
    @classmethod
    def _sanitize_metadata(cls, value: object) -> object:
        if value is None:
            return {}
        return _sanitize_audit_metadata(value)

    def to_audit_actor(self) -> AuditActor:
        return AuditActor(actor_type=self.actor_type, actor_id=self.actor_id)


class AuditEntity(InspectionModel):
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)

    @field_validator("entity_type", "entity_id", mode="before")
    @classmethod
    def _normalize_entity_text(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="entity field")


class AuditRelatedIds(InspectionModel):
    source_work_id: str | None = None
    character_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    context_package_id: str | None = None
    persona_version_id: str | None = None
    critic_report_id: str | None = None
    llm_trace_id: str | None = None
    evaluation_run_id: str | None = None
    retrieval_evaluation_run_id: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_optional_id(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_required_text(value, field_name="related id")


class AuditEventPayload(InspectionModel):
    id: str = Field(default_factory=lambda: _generate_audit_event_id(), min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    actor: AuditActor
    operation: AuditOperation | str
    entity: AuditEntity
    related_ids: AuditRelatedIds = Field(default_factory=AuditRelatedIds)
    reason: str = Field(min_length=1)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    persistence: Literal["payload_only"] = BATCH_04_AUDIT_PERSISTENCE_DECISION

    @field_validator("id", "operation", "reason", mode="before")
    @classmethod
    def _normalize_required_text_field(cls, value: object) -> object:
        return _normalize_required_text(value, field_name="audit field")

    @field_validator("metadata", mode="before")
    @classmethod
    def _sanitize_metadata(cls, value: object) -> object:
        if value is None:
            return {}
        return _sanitize_audit_metadata(value)


def require_local_actor_context(
    actor_context: LocalActorContext | None,
    *,
    require_user_id: bool = False,
) -> LocalActorContext:
    if actor_context is None:
        raise ValueError("local actor context is required")
    if require_user_id and actor_context.user_id is None:
        raise ValueError("local actor context user_id is required")
    return actor_context


def require_operation_reason(
    reason: str | None,
    *,
    field_name: str = "reason",
) -> str:
    if reason is None:
        raise ValueError(f"{field_name} is required")
    if not isinstance(reason, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = reason.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def build_audit_metadata(
    metadata: dict[str, Any] | None = None,
    *,
    actor_context: LocalActorContext | None = None,
    correlation: CorrelationContext | WorkflowContext | None = None,
    result: AuditResult | str | None = AuditResult.SUCCEEDED,
) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    if metadata:
        combined.update(_sanitize_audit_metadata(metadata))
    if actor_context is not None:
        if actor_context.actor_label is not None:
            combined["actor_label"] = actor_context.actor_label
        if actor_context.user_id is not None:
            combined["actor_user_id"] = actor_context.user_id
        if actor_context.metadata:
            combined["actor_metadata"] = actor_context.metadata
    if correlation is not None:
        combined["request_id"] = correlation.request_id
        if correlation.workflow_id is not None:
            combined["workflow_id"] = correlation.workflow_id
        if correlation.workflow_type is not None:
            combined["workflow_type"] = correlation.workflow_type
        if correlation.status is not None:
            combined["workflow_status"] = str(correlation.status)
    if result is not None:
        combined["result"] = _normalize_required_text(
            str(result),
            field_name="audit result",
        )
    return _sanitize_audit_metadata(combined)


def build_memory_review_audit_event(
    *,
    actor: AuditActor | LocalActorContext | Mapping[str, Any],
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation: CorrelationContext | WorkflowContext | None = None,
    result: AuditResult | str = AuditResult.SUCCEEDED,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_REVIEW,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        correlation=correlation,
        result=result,
        event_id=event_id,
    )


def build_memory_edit_audit_event(
    *,
    actor: AuditActor | LocalActorContext | Mapping[str, Any],
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation: CorrelationContext | WorkflowContext | None = None,
    result: AuditResult | str = AuditResult.SUCCEEDED,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_EDIT,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        correlation=correlation,
        result=result,
        event_id=event_id,
    )


def build_memory_archive_audit_event(
    *,
    actor: AuditActor | LocalActorContext | Mapping[str, Any],
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation: CorrelationContext | WorkflowContext | None = None,
    result: AuditResult | str = AuditResult.SUCCEEDED,
    event_id: str | None = None,
) -> AuditEventPayload:
    return build_manual_memory_audit_event(
        operation=AuditOperation.MEMORY_ARCHIVE,
        actor=actor,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata,
        correlation=correlation,
        result=result,
        event_id=event_id,
    )


def build_manual_memory_audit_event(
    *,
    operation: AuditOperation | str,
    actor: AuditActor | LocalActorContext | Mapping[str, Any],
    before: Memory | MemorySummary,
    after: Memory | MemorySummary,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation: CorrelationContext | WorkflowContext | None = None,
    result: AuditResult | str = AuditResult.SUCCEEDED,
    event_id: str | None = None,
) -> AuditEventPayload:
    actor_context = _coerce_local_actor_context(actor)
    audit_actor = actor_context.to_audit_actor() if actor_context is not None else actor
    event_reason = _resolve_event_reason(reason=reason, actor_context=actor_context)
    before_snapshot = _memory_snapshot(before)
    after_snapshot = _memory_snapshot(after)
    _validate_same_memory_boundary(before_snapshot, after_snapshot)

    return AuditEventPayload(
        id=event_id if event_id is not None else _generate_audit_event_id(),
        actor=audit_actor,
        operation=operation,
        entity=AuditEntity(
            entity_type="memory",
            entity_id=after_snapshot["id"],
        ),
        related_ids=AuditRelatedIds(
            user_id=after_snapshot["user_id"],
            character_id=after_snapshot["character_id"],
            conversation_id=after_snapshot.get("conversation_id"),
        ),
        reason=event_reason,
        before=before_snapshot,
        after=after_snapshot,
        metadata=build_audit_metadata(
            metadata,
            actor_context=actor_context,
            correlation=correlation,
            result=result,
        ),
    )


def _memory_snapshot(memory: Memory | MemorySummary) -> dict[str, Any]:
    return memory.model_dump(mode="json")


def _validate_same_memory_boundary(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> None:
    fields = ("id", "user_id", "character_id", "conversation_id", "scope")
    mismatched_fields = [
        field
        for field in fields
        if before_snapshot.get(field) != after_snapshot.get(field)
    ]
    if mismatched_fields:
        joined_fields = ", ".join(mismatched_fields)
        raise ValueError(f"memory audit before/after snapshots must preserve: {joined_fields}")


def _generate_audit_event_id() -> str:
    return f"audit_{uuid4().hex}"


def _coerce_local_actor_context(
    actor: AuditActor | LocalActorContext | Mapping[str, Any],
) -> LocalActorContext | None:
    if isinstance(actor, LocalActorContext):
        return actor
    if isinstance(actor, Mapping):
        return LocalActorContext.model_validate(actor)
    return None


def _resolve_event_reason(
    *,
    reason: str | None,
    actor_context: LocalActorContext | None,
) -> str:
    if reason is not None:
        return reason
    if actor_context is not None and actor_context.operation_reason is not None:
        return actor_context.operation_reason
    raise ValueError("reason is required for audit event")


def _normalize_required_text(value: object, *, field_name: str) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _normalize_optional_text(value: object, *, field_name: str) -> object:
    if value is None:
        return None
    return _normalize_required_text(value, field_name=field_name)


_REDACTED_AUTH_HEADER = "[redacted:auth_header]"
_REDACTED_DATABASE_URL = "[redacted:database_url]"
_REDACTED_PATH = "[redacted:path]"
_REDACTED_PROMPT = "[redacted:prompt]"
_REDACTED_PROVIDER_CONFIG = "[redacted:provider_config]"
_REDACTED_PROVIDER_PAYLOAD = "[redacted:provider_payload]"
_REDACTED_SECRET = "[redacted:secret]"
_REDACTED_STACK_TRACE = "[redacted:stack_trace]"
_REDACTED_TRACE_PAYLOAD = "[redacted:trace_payload]"

_AUTH_HEADER_METADATA_KEYS = {
    "authorization",
    "auth_header",
    "auth_headers",
    "request_headers",
    "provider_headers",
    "headers",
}
_COOKIE_METADATA_KEYS = {"cookie", "cookies", "set_cookie", "set_cookies"}
_DATABASE_URL_METADATA_KEYS = {
    "database_url",
    "db_url",
    "sqlalchemy_url",
    "connection_string",
    "connection_url",
}
_PROVIDER_CONFIG_METADATA_KEYS = {
    "provider_config",
    "provider_settings",
    "raw_provider_config",
    "openai_config",
    "llm_config",
    "embedding_config",
    "provider_options",
    "base_url",
    "endpoint_url",
    "organization_id",
    "project_id",
}
_PROVIDER_PAYLOAD_METADATA_KEYS = {
    "provider_payload",
    "provider_request",
    "provider_response",
    "provider_request_payload",
    "provider_response_payload",
    "raw_provider_request",
    "raw_provider_response",
    "raw_provider_payload",
    "raw_provider_output",
}
_PROMPT_METADATA_KEYS = {
    "prompt",
    "assembled_prompt",
    "raw_prompt",
    "prompt_payload",
    "system_message",
}
_PATH_METADATA_KEYS = {"path", "file_path", "config_file", "source_path", "local_path"}
_STACK_TRACE_METADATA_KEYS = {"stack_trace", "stacktrace", "traceback", "call_stack", "exc_info"}
_TRACE_PAYLOAD_METADATA_KEYS = {
    "raw_output",
    "parsed_output",
    "response_schema",
    "validation_errors",
    "raw_trace_payload",
    "trace_payload",
}

_DATABASE_URL_PATTERN = re.compile(
    r"\b(?:sqlite|postgresql|postgres|mysql|mariadb|mssql|oracle)"
    r"(?:\+[a-z0-9_]+)?://[^\s'\"<>]+",
    re.IGNORECASE,
)
_URL_WITH_CREDENTIALS_PATTERN = re.compile(
    r"\b([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^/\s@]+)@",
    re.IGNORECASE,
)
_WINDOWS_PATH_PATTERN = re.compile(
    r"(?<![\w/])(?:[a-zA-Z]:[\\/](?:[^\\/\s'\"<>|?*]+[\\/]?)+)"
)
_POSIX_PATH_PATTERN = re.compile(
    r"(?<![\w:/])/(?:Users|home|var|tmp|etc|opt|mnt|Volumes|private|data|root|"
    r"workspace|projects)/[^\s'\"<>]+"
)
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|secret|password|authorization|cookie)[\"']?\s*[:=]\s*)"
    r"([\"']?)[^,\"'\s}\]]+(\2)"
)
_ENV_SECRET_PATTERN = re.compile(
    r"\b(PJ_[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))\s*=\s*[^\s,;]+"
)
_OPENAI_STYLE_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")


def _sanitize_audit_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_audit_metadata_field(key, field_value)
            for key, field_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_sanitize_audit_metadata(item) for item in value]
    if isinstance(value, str):
        return _scrub_sensitive_string(value)
    return value


def _sanitize_audit_metadata_field(key: Any, value: Any) -> Any:
    normalized_key = _normalize_metadata_key(key)
    if _is_auth_header_key(normalized_key):
        return _REDACTED_AUTH_HEADER
    if normalized_key in _COOKIE_METADATA_KEYS:
        return _REDACTED_AUTH_HEADER
    if _is_secret_key(normalized_key):
        return _REDACTED_SECRET
    if normalized_key in _DATABASE_URL_METADATA_KEYS:
        return _REDACTED_DATABASE_URL
    if normalized_key in _PROVIDER_CONFIG_METADATA_KEYS:
        return _REDACTED_PROVIDER_CONFIG
    if normalized_key in _PROVIDER_PAYLOAD_METADATA_KEYS:
        return _REDACTED_PROVIDER_PAYLOAD
    if _is_prompt_key(normalized_key):
        return _REDACTED_PROMPT
    if normalized_key in _PATH_METADATA_KEYS:
        return _REDACTED_PATH
    if normalized_key in _STACK_TRACE_METADATA_KEYS:
        return _REDACTED_STACK_TRACE
    if normalized_key in _TRACE_PAYLOAD_METADATA_KEYS:
        return _REDACTED_TRACE_PAYLOAD
    return _sanitize_audit_metadata(value)


def _is_auth_header_key(key: str) -> bool:
    return key in _AUTH_HEADER_METADATA_KEYS or key.endswith("_authorization")


def _is_secret_key(key: str) -> bool:
    if key in {"token", "tokens", "secret", "secrets", "password", "credential", "credentials"}:
        return True
    secret_fragments = (
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "private_key",
        "signing_key",
        "session_token",
        "bearer_token",
    )
    return any(fragment in key for fragment in secret_fragments)


def _is_prompt_key(key: str) -> bool:
    return key in _PROMPT_METADATA_KEYS or key.endswith("_prompt")


def _normalize_metadata_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _scrub_sensitive_string(value: str) -> str:
    if "Traceback (most recent call last)" in value:
        return _REDACTED_STACK_TRACE
    scrubbed = _DATABASE_URL_PATTERN.sub(_REDACTED_DATABASE_URL, value)
    scrubbed = _URL_WITH_CREDENTIALS_PATTERN.sub(
        r"\1[redacted:credentials]@",
        scrubbed,
    )
    scrubbed = _BEARER_PATTERN.sub(f"Bearer {_REDACTED_SECRET}", scrubbed)
    scrubbed = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED_SECRET}{match.group(3)}",
        scrubbed,
    )
    scrubbed = _ENV_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={_REDACTED_SECRET}",
        scrubbed,
    )
    scrubbed = _OPENAI_STYLE_KEY_PATTERN.sub(_REDACTED_SECRET, scrubbed)
    scrubbed = _WINDOWS_PATH_PATTERN.sub(_REDACTED_PATH, scrubbed)
    scrubbed = _POSIX_PATH_PATTERN.sub(_REDACTED_PATH, scrubbed)
    return scrubbed
