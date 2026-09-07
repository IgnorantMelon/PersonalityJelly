from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from personality_jelly.application.inspection import InspectionModel


MAX_ERROR_CODE_LENGTH = 128
MAX_ERROR_MESSAGE_LENGTH = 500
MAX_ERROR_STEP_LENGTH = 128
MAX_RETRY_HINT_LENGTH = 256


class WorkflowFailureCode(StrEnum):
    PROVIDER_FAILURE = "provider_failure"
    PROVIDER_VALIDATION_ERROR = "provider_validation_error"
    PARTIAL_PERSISTENCE = "partial_persistence"
    RETRYABLE_CONFLICT = "retryable_conflict"
    CRITIC_FAILURE = "critic_failure"
    GUARD_FAILURE = "guard_failure"


class WorkflowFailureDetails(InspectionModel):
    error_family: WorkflowFailureCode | str = Field(
        min_length=1,
        max_length=MAX_ERROR_CODE_LENGTH,
    )
    error_code: str = Field(min_length=1, max_length=MAX_ERROR_CODE_LENGTH)
    failed_step: str | None = Field(default=None, max_length=MAX_ERROR_STEP_LENGTH)
    workflow_id: str | None = Field(default=None, max_length=MAX_ERROR_CODE_LENGTH)
    persisted_ids: dict[str, Any] = Field(default_factory=dict)
    llm_trace_ids: list[str] = Field(default_factory=list)
    audit_event_ids: list[str] = Field(default_factory=list)
    retry_hint: str | None = Field(default=None, max_length=MAX_RETRY_HINT_LENGTH)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "error_family",
        "error_code",
        "failed_step",
        "workflow_id",
        "retry_hint",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, StrEnum):
            value = str(value)
        if isinstance(value, str):
            stripped = sanitize_error_message(value.strip())
            if not stripped:
                raise ValueError("error detail text must not be blank")
            return stripped
        return value

    @field_validator("llm_trace_ids", "audit_event_ids", mode="before")
    @classmethod
    def _normalize_id_list(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list | tuple):
            raise ValueError("error detail ids must be a list")
        return [_normalize_id(item) for item in value]

    @field_validator("persisted_ids", "details", mode="before")
    @classmethod
    def _sanitize_mapping(cls, value: object) -> object:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("error details must be a mapping")
        return sanitize_error_details(value)


class PartialPersistenceDetails(WorkflowFailureDetails):
    error_family: WorkflowFailureCode | str = WorkflowFailureCode.PARTIAL_PERSISTENCE


class ConflictError(RuntimeError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(sanitize_error_message(message))
        self.details = sanitize_error_details(details or {})


class WorkflowFailureError(RuntimeError):
    normalized_code: WorkflowFailureCode = WorkflowFailureCode.PROVIDER_FAILURE
    default_message = "Provider-backed workflow failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: WorkflowFailureDetails | Mapping[str, Any] | None = None,
    ) -> None:
        failure_details = _coerce_workflow_failure_details(
            details,
            error_family=self.normalized_code,
        )
        self.failure_details = failure_details
        super().__init__(sanitize_error_message(message or self.default_message))


class ProviderFailureError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.PROVIDER_FAILURE
    default_message = "Provider call failed"


class ProviderValidationFailureError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.PROVIDER_VALIDATION_ERROR
    default_message = "Provider output failed schema validation"


class PartialPersistenceError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.PARTIAL_PERSISTENCE
    default_message = "Workflow failed after partial persistence"


class RetryableConflictError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.RETRYABLE_CONFLICT
    default_message = "Workflow retry conflicted with persisted state"


class CriticFailureError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.CRITIC_FAILURE
    default_message = "Required critic follow-up failed"


class GuardFailureError(WorkflowFailureError):
    normalized_code = WorkflowFailureCode.GUARD_FAILURE
    default_message = "Required guard follow-up failed"


@dataclass(frozen=True)
class NormalizedError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize_error(error: Exception) -> NormalizedError:
    if isinstance(error, WorkflowFailureError):
        return NormalizedError(
            code=str(error.normalized_code),
            message=sanitize_error_message(str(error)),
            details=error.failure_details.model_dump(
                mode="json",
                exclude_none=True,
            ),
        )
    if isinstance(error, ConflictError):
        return NormalizedError(
            code="conflict",
            message=sanitize_error_message(str(error)),
            details=error.details,
        )
    if isinstance(error, LookupError):
        return NormalizedError(code="not_found", message=sanitize_error_message(str(error)))
    if isinstance(error, ValueError):
        return NormalizedError(
            code="validation_error",
            message=sanitize_error_message(str(error)),
        )
    return NormalizedError(
        code="unexpected_error",
        message=sanitize_error_message(str(error)) or error.__class__.__name__,
        details={"exception_type": error.__class__.__name__},
    )


def build_provider_failure_details(
    *,
    error_family: WorkflowFailureCode | str = WorkflowFailureCode.PROVIDER_FAILURE,
    error_code: str | None = None,
    failed_step: str | None = None,
    workflow_id: str | None = None,
    persisted_ids: Mapping[str, Any] | None = None,
    llm_trace_ids: Sequence[str] | None = None,
    audit_event_ids: Sequence[str] | None = None,
    retry_hint: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> WorkflowFailureDetails:
    family = _normalize_text(str(error_family), field_name="error_family")
    code = _normalize_text(error_code or family, field_name="error_code")
    return WorkflowFailureDetails(
        error_family=family,
        error_code=code,
        failed_step=failed_step,
        workflow_id=workflow_id,
        persisted_ids=dict(persisted_ids or {}),
        llm_trace_ids=list(llm_trace_ids or []),
        audit_event_ids=list(audit_event_ids or []),
        retry_hint=retry_hint,
        details=dict(details or {}),
    )


def build_partial_persistence_details(
    *,
    failed_step: str,
    error_code: str = "workflow_step_failed",
    workflow_id: str | None = None,
    persisted_ids: Mapping[str, Any] | None = None,
    llm_trace_ids: Sequence[str] | None = None,
    audit_event_ids: Sequence[str] | None = None,
    retry_hint: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> PartialPersistenceDetails:
    base = build_provider_failure_details(
        error_family=WorkflowFailureCode.PARTIAL_PERSISTENCE,
        error_code=error_code,
        failed_step=failed_step,
        workflow_id=workflow_id,
        persisted_ids=persisted_ids,
        llm_trace_ids=llm_trace_ids,
        audit_event_ids=audit_event_ids,
        retry_hint=retry_hint,
        details=details,
    )
    return PartialPersistenceDetails(**base.model_dump(mode="python"))


def sanitize_error_details(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_error_field(key, field_value)
            for key, field_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [sanitize_error_details(item) for item in value]
    if isinstance(value, str):
        return sanitize_error_message(value)
    return value


def sanitize_error_message(value: str) -> str:
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


def _coerce_workflow_failure_details(
    details: WorkflowFailureDetails | Mapping[str, Any] | None,
    *,
    error_family: WorkflowFailureCode,
) -> WorkflowFailureDetails:
    if isinstance(details, WorkflowFailureDetails):
        if str(details.error_family) == str(error_family):
            return details
        return details.model_copy(update={"error_family": error_family})
    payload = dict(details or {})
    payload.setdefault("error_family", error_family)
    payload.setdefault("error_code", str(error_family))
    return WorkflowFailureDetails.model_validate(payload)


def _sanitize_error_field(key: Any, value: Any) -> Any:
    normalized_key = _normalize_key(key)
    if _is_auth_header_key(normalized_key):
        return _REDACTED_AUTH_HEADER
    if normalized_key in _COOKIE_KEYS:
        return _REDACTED_AUTH_HEADER
    if _is_secret_key(normalized_key):
        return _REDACTED_SECRET
    if normalized_key in _DATABASE_URL_KEYS:
        return _REDACTED_DATABASE_URL
    if normalized_key in _PROVIDER_CONFIG_KEYS:
        return _REDACTED_PROVIDER_CONFIG
    if normalized_key in _PROVIDER_PAYLOAD_KEYS:
        return _REDACTED_PROVIDER_PAYLOAD
    if _is_prompt_key(normalized_key):
        return _REDACTED_PROMPT
    if normalized_key in _PATH_KEYS:
        return _REDACTED_PATH
    if normalized_key in _STACK_TRACE_KEYS:
        return _REDACTED_STACK_TRACE
    if normalized_key in _TRACE_PAYLOAD_KEYS:
        return _REDACTED_TRACE_PAYLOAD
    if normalized_key in _SOURCE_TEXT_KEYS:
        return _REDACTED_SOURCE_TEXT
    if normalized_key in _MEMORY_CONTENT_KEYS:
        return _REDACTED_USER_TEXT
    if normalized_key in _CONTENT_KEYS:
        return _REDACTED_USER_TEXT
    return sanitize_error_details(value)


def _normalize_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("error detail id must be a string")
    return _normalize_text(value, field_name="error detail id")


def _normalize_text(value: str, *, field_name: str) -> str:
    normalized = sanitize_error_message(value.strip())
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > MAX_ERROR_CODE_LENGTH:
        raise ValueError(f"{field_name} must be at most {MAX_ERROR_CODE_LENGTH} characters")
    return normalized


def _is_auth_header_key(key: str) -> bool:
    return key in _AUTH_HEADER_KEYS or key.endswith("_authorization")


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
    return key == "prompt" or key.endswith("_prompt") or key in _PROMPT_KEYS


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


_REDACTED_AUTH_HEADER = "[redacted:auth_header]"
_REDACTED_DATABASE_URL = "[redacted:database_url]"
_REDACTED_PATH = "[redacted:path]"
_REDACTED_PROMPT = "[redacted:prompt]"
_REDACTED_PROVIDER_CONFIG = "[redacted:provider_config]"
_REDACTED_PROVIDER_PAYLOAD = "[redacted:provider_payload]"
_REDACTED_SECRET = "[redacted:secret]"
_REDACTED_SOURCE_TEXT = "[redacted:source_text]"
_REDACTED_STACK_TRACE = "[redacted:stack_trace]"
_REDACTED_TRACE_PAYLOAD = "[redacted:trace_payload]"
_REDACTED_USER_TEXT = "[redacted:user_text]"

_AUTH_HEADER_KEYS = {
    "authorization",
    "auth_header",
    "auth_headers",
    "request_headers",
    "provider_headers",
    "headers",
}
_COOKIE_KEYS = {"cookie", "cookies", "set_cookie", "set_cookies"}
_DATABASE_URL_KEYS = {
    "database_url",
    "db_url",
    "sqlalchemy_url",
    "connection_string",
    "connection_url",
}
_PROVIDER_CONFIG_KEYS = {
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
_PROVIDER_PAYLOAD_KEYS = {
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
_PROMPT_KEYS = {
    "assembled_prompt",
    "raw_prompt",
    "prompt_payload",
    "system_message",
    "developer_message",
    "messages",
}
_PATH_KEYS = {"path", "file_path", "config_file", "source_path", "local_path"}
_STACK_TRACE_KEYS = {"stack_trace", "stacktrace", "traceback", "call_stack", "exc_info"}
_TRACE_PAYLOAD_KEYS = {
    "raw_output",
    "parsed_output",
    "response_schema",
    "validation_errors",
    "raw_trace_payload",
    "trace_payload",
}
_SOURCE_TEXT_KEYS = {
    "source_text",
    "source_chunk_text",
    "chunk_text",
    "full_source_chunk",
    "full_source_chunks",
    "source_chunks",
}
_MEMORY_CONTENT_KEYS = {
    "memory_content",
    "memory_contents",
    "full_memory",
    "full_memory_content",
    "memories",
}
_CONTENT_KEYS = {"content", "message_content", "user_text", "user_message"}

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
