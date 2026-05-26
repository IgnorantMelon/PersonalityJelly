from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


REDACTED_AUTH_HEADER = "[redacted:auth_header]"
REDACTED_COOKIE = "[redacted:auth_header]"
REDACTED_DATABASE_URL = "[redacted:database_url]"
REDACTED_INTERNAL_ERROR = "[redacted:internal_error]"
REDACTED_PATH = "[redacted:path]"
REDACTED_PROMPT = "[redacted:prompt]"
REDACTED_PROVIDER_CONFIG = "[redacted:provider_config]"
REDACTED_PROVIDER_LABEL = "[redacted:provider_label]"
REDACTED_PROVIDER_PAYLOAD = "[redacted:provider_payload]"
REDACTED_REASON = "[redacted:reason]"
REDACTED_SECRET = "[redacted:secret]"
REDACTED_SOURCE_TEXT = "[redacted:source_text]"
REDACTED_STACK_TRACE = "[redacted:stack_trace]"
REDACTED_TRACE_PAYLOAD = "[redacted:trace_payload]"
REDACTED_USER_TEXT = "[redacted:user_text]"


class RedactionProfileName(StrEnum):
    LOCAL_DEFAULT = "local_default"
    LOCAL_DEBUG = "local_debug"
    PLATFORM_DEFAULT = "platform_default"


class RedactionProfile(BaseModel):
    """Transport-neutral policy for API response serialization."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    name: RedactionProfileName
    redact_prompts: bool = True
    redact_raw_user_text: bool = True
    redact_memory_content: bool = True
    redact_memory_reason: bool = True
    redact_source_text: bool = True
    redact_source_previews: bool = False
    redact_trace_payloads: bool = True
    redact_provider_payloads: bool = True
    redact_provider_labels: bool = False
    redact_reason_text: bool = True


LOCAL_DEFAULT_REDACTION_PROFILE = RedactionProfile(
    name=RedactionProfileName.LOCAL_DEFAULT,
)
LOCAL_DEBUG_REDACTION_PROFILE = RedactionProfile(
    name=RedactionProfileName.LOCAL_DEBUG,
    redact_prompts=False,
    redact_raw_user_text=False,
    redact_memory_content=False,
    redact_memory_reason=False,
    redact_source_text=False,
    redact_source_previews=False,
    redact_trace_payloads=False,
    redact_provider_payloads=False,
    redact_provider_labels=False,
    redact_reason_text=False,
)
PLATFORM_DEFAULT_REDACTION_PROFILE = RedactionProfile(
    name=RedactionProfileName.PLATFORM_DEFAULT,
    redact_source_previews=True,
    redact_provider_labels=True,
)

_PROFILE_BY_NAME: dict[RedactionProfileName, RedactionProfile] = {
    RedactionProfileName.LOCAL_DEFAULT: LOCAL_DEFAULT_REDACTION_PROFILE,
    RedactionProfileName.LOCAL_DEBUG: LOCAL_DEBUG_REDACTION_PROFILE,
    RedactionProfileName.PLATFORM_DEFAULT: PLATFORM_DEFAULT_REDACTION_PROFILE,
}

_AUTH_HEADER_KEYS = {
    "authorization",
    "auth_header",
    "auth_headers",
    "request_headers",
    "provider_headers",
    "headers",
    "www_authenticate",
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
}
_STACK_TRACE_KEYS = {
    "stack_trace",
    "stacktrace",
    "traceback",
    "call_stack",
    "exc_info",
}
_INTERNAL_ERROR_KEYS = {
    "exception",
    "exception_details",
    "exception_type",
    "internal_error",
    "internal_exception",
    "raw_error",
    "error_body",
    "provider_error_body",
    "sql",
    "sql_statement",
}
_TRACE_PAYLOAD_KEYS = {
    "raw_output",
    "parsed_output",
    "response_schema",
    "validation_errors",
    "raw_trace_payload",
    "trace_payload",
}
_PROVIDER_LABEL_KEYS = {"provider_name", "model_name", "embedding_model"}
_SOURCE_TEXT_KEYS = {"text", "chunk_text", "source_text", "full_text"}
_SOURCE_PREVIEW_KEYS = {"text_preview", "chunk_preview", "excerpt", "source_excerpt"}
_REASON_KEYS = {"reason", "reasons", "notes", "reasoning"}
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


def get_redaction_profile(
    profile: RedactionProfile | RedactionProfileName | str | None = None,
) -> RedactionProfile:
    if profile is None:
        return LOCAL_DEFAULT_REDACTION_PROFILE
    if isinstance(profile, RedactionProfile):
        return profile
    try:
        profile_name = RedactionProfileName(profile)
    except ValueError as exc:
        supported = ", ".join(profile.value for profile in RedactionProfileName)
        message = f"unsupported redaction profile {profile!r}; expected one of {supported}"
        raise ValueError(message) from exc
    return _PROFILE_BY_NAME[profile_name]


def redact_payload(
    value: Any,
    *,
    profile: RedactionProfile | RedactionProfileName | str | None = None,
) -> Any:
    """Return a recursively redacted copy of dict/list/Pydantic payloads."""

    return _redact_value(value, profile=get_redaction_profile(profile), path=(), parent=None)


def _redact_value(
    value: Any,
    *,
    profile: RedactionProfile,
    path: tuple[str, ...],
    parent: Mapping[str, Any] | None,
) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    if isinstance(value, Mapping):
        return {
            str(key): _redact_field(
                key,
                field_value,
                profile=profile,
                path=path,
                parent=value,
            )
            for key, field_value in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            _redact_value(item, profile=profile, path=path, parent=parent)
            for item in value
        ]

    if isinstance(value, str):
        return _scrub_sensitive_string(value)

    return value


def _redact_field(
    key: Any,
    value: Any,
    *,
    profile: RedactionProfile,
    path: tuple[str, ...],
    parent: Mapping[str, Any],
) -> Any:
    normalized_key = _normalize_key(key)
    field_path = (*path, normalized_key)
    marker = _marker_for_field(
        normalized_key,
        value,
        profile=profile,
        path=field_path,
        parent=parent,
    )
    if marker is not None:
        return marker
    return _redact_value(value, profile=profile, path=field_path, parent=parent)


def _marker_for_field(
    key: str,
    value: Any,
    *,
    profile: RedactionProfile,
    path: tuple[str, ...],
    parent: Mapping[str, Any],
) -> str | None:
    if _is_auth_header_key(key):
        return REDACTED_AUTH_HEADER
    if _is_cookie_key(key):
        return REDACTED_COOKIE
    if _is_secret_key(key):
        return REDACTED_SECRET
    if key in _DATABASE_URL_KEYS:
        return REDACTED_DATABASE_URL
    if key in _PROVIDER_CONFIG_KEYS:
        return REDACTED_PROVIDER_CONFIG
    if key in _STACK_TRACE_KEYS:
        return REDACTED_STACK_TRACE
    if key in _INTERNAL_ERROR_KEYS:
        return REDACTED_INTERNAL_ERROR
    if profile.redact_provider_payloads and key in _PROVIDER_PAYLOAD_KEYS:
        return REDACTED_PROVIDER_PAYLOAD
    if profile.redact_trace_payloads and key in _TRACE_PAYLOAD_KEYS:
        return REDACTED_TRACE_PAYLOAD
    if profile.redact_provider_labels and key in _PROVIDER_LABEL_KEYS:
        return REDACTED_PROVIDER_LABEL
    if profile.redact_prompts and _is_prompt_key(key):
        return REDACTED_PROMPT
    if profile.redact_memory_content and key == "content" and _is_memory_context(path, parent):
        return REDACTED_USER_TEXT
    if profile.redact_memory_reason and key == "reason" and _is_memory_context(path, parent):
        return REDACTED_REASON
    if profile.redact_raw_user_text and _is_user_text_key(key, path, parent):
        return REDACTED_USER_TEXT
    if profile.redact_source_text and _is_source_text_key(key, path, parent):
        return REDACTED_SOURCE_TEXT
    if profile.redact_source_previews and _is_source_preview_key(key, path, parent):
        return REDACTED_SOURCE_TEXT
    if profile.redact_reason_text and key in _REASON_KEYS:
        return REDACTED_REASON
    if profile.name == RedactionProfileName.PLATFORM_DEFAULT and key in _CONTENT_KEYS:
        return REDACTED_USER_TEXT
    return _marker_for_sensitive_string_value(key, value)


def _marker_for_sensitive_string_value(key: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if _DATABASE_URL_PATTERN.search(value):
        return REDACTED_DATABASE_URL
    if "Traceback (most recent call last)" in value:
        return REDACTED_STACK_TRACE
    if key in {"path", "file_path", "config_file", "source_path", "local_path"}:
        return REDACTED_PATH
    return None


def _is_auth_header_key(key: str) -> bool:
    return key in _AUTH_HEADER_KEYS or key.endswith("_authorization")


def _is_cookie_key(key: str) -> bool:
    return key in _COOKIE_KEYS


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
    return (
        key == "prompt"
        or key.endswith("_prompt")
        or key in {"assembled_prompt", "raw_prompt", "prompt_payload", "system_message"}
    )


def _is_user_text_key(key: str, path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    if key in {"user_text", "user_message", "current_user_message"}:
        return True
    if key in {"query", "prompt"} and _path_contains(path, "eval", "benchmark", "case"):
        return True
    if key == "content" and _is_message_context(path, parent):
        return True
    if key == "summary" or key.startswith("summary_"):
        return True
    return key in {
        "short_term_scene_state",
        "user_memory_candidates",
        "relationship_memory_notes",
        "reflective_notes",
    }


def _is_message_context(path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    parent_keys = {_normalize_key(key) for key in parent}
    if {"role", "conversation_id", "created_at"}.issubset(parent_keys):
        return True
    return _path_contains(path, "message", "messages")


def _is_memory_context(path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    parent_keys = {_normalize_key(key) for key in parent}
    if {"scope", "status", "importance"}.issubset(parent_keys):
        return True
    return _path_contains(path, "memory", "memories")


def _is_source_text_key(key: str, path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    if key not in _SOURCE_TEXT_KEYS:
        return False
    return _is_source_context(path, parent)


def _is_source_preview_key(key: str, path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    if key not in _SOURCE_PREVIEW_KEYS:
        return False
    return _is_source_context(path, parent) or key in {"excerpt", "source_excerpt"}


def _is_source_context(path: tuple[str, ...], parent: Mapping[str, Any]) -> bool:
    parent_keys = {_normalize_key(key) for key in parent}
    if "source_work_id" in parent_keys and (
        "paragraph_index" in parent_keys or "chunk_id" in parent_keys
    ):
        return True
    return _path_contains(path, "source", "chunk", "chunks", "evidence")


def _path_contains(path: tuple[str, ...], *needles: str) -> bool:
    return any(any(needle in part for needle in needles) for part in path)


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _scrub_sensitive_string(value: str) -> str:
    if "Traceback (most recent call last)" in value:
        return REDACTED_STACK_TRACE
    scrubbed = _DATABASE_URL_PATTERN.sub(REDACTED_DATABASE_URL, value)
    scrubbed = _URL_WITH_CREDENTIALS_PATTERN.sub(r"\1[redacted:credentials]@", scrubbed)
    scrubbed = _BEARER_PATTERN.sub(f"Bearer {REDACTED_SECRET}", scrubbed)
    scrubbed = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED_SECRET}{match.group(3)}",
        scrubbed,
    )
    scrubbed = _ENV_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED_SECRET}",
        scrubbed,
    )
    scrubbed = _OPENAI_STYLE_KEY_PATTERN.sub(REDACTED_SECRET, scrubbed)
    scrubbed = _WINDOWS_PATH_PATTERN.sub(REDACTED_PATH, scrubbed)
    scrubbed = _POSIX_PATH_PATTERN.sub(REDACTED_PATH, scrubbed)
    return scrubbed
