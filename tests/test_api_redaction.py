from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from personality_jelly.api.redaction import (
    REDACTED_AUTH_HEADER,
    REDACTED_DATABASE_URL,
    REDACTED_PATH,
    REDACTED_PROMPT,
    REDACTED_PROVIDER_CONFIG,
    REDACTED_PROVIDER_LABEL,
    REDACTED_PROVIDER_PAYLOAD,
    REDACTED_REASON,
    REDACTED_SECRET,
    REDACTED_SOURCE_TEXT,
    REDACTED_STACK_TRACE,
    REDACTED_TRACE_PAYLOAD,
    REDACTED_USER_TEXT,
    RedactionProfileName,
    get_redaction_profile,
    redact_payload,
)
from personality_jelly.application import ContextPackageDetail, MemorySummary, SourceChunkDetail
from personality_jelly.domain import InteractionMode, MemoryScope, MemoryStatus


NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def test_redaction_profile_names_define_safe_defaults_and_debug_scope() -> None:
    local_default = get_redaction_profile("local_default")
    local_debug = get_redaction_profile(RedactionProfileName.LOCAL_DEBUG)
    platform_default = get_redaction_profile("platform_default")

    assert local_default.name == "local_default"
    assert local_default.redact_prompts is True
    assert local_default.redact_source_previews is False
    assert local_debug.name == "local_debug"
    assert local_debug.redact_prompts is False
    assert local_debug.redact_trace_payloads is False
    assert platform_default.name == "platform_default"
    assert platform_default.redact_provider_labels is True
    assert platform_default.redact_source_previews is True


def test_local_default_recursively_redacts_sensitive_dict_and_list_payloads() -> None:
    payload = {
        "id": "write_001",
        "status": "accepted",
        "authorization": "Bearer sk-live-secret",
        "database_url": "sqlite:///C:/Users/figna/private/pjelly.db",
        "provider_config": {
            "base_url": "https://user:pass@example.test/v1",
            "api_key": "sk-provider-secret",
        },
        "messages": [
            {
                "id": "msg_001",
                "conversation_id": "conv_001",
                "role": "user",
                "content": "My private address is in the message.",
                "created_at": "2026-05-26T12:00:00Z",
            }
        ],
        "memory": {
            "id": "mem_001",
            "scope": "user_memory",
            "status": "accepted",
            "importance": 0.9,
            "content": "User likes late-night writing.",
            "reason": "User said this directly.",
        },
        "context": {
            "assembled_prompt": "system prompt with user text",
            "raw_output": {"text": "provider echoed private payload"},
        },
        "source_chunk": {
            "id": "chunk_001",
            "source_work_id": "sw_001",
            "paragraph_index": 1,
            "text": "Full copyrighted source text.",
            "text_preview": "Short source preview.",
        },
        "error": {
            "stack_trace": "Traceback (most recent call last):\n  File \"C:\\Users\\figna\\x.py\"",
            "message": "failed while opening C:\\Users\\figna\\secrets\\config.toml",
        },
        "provider_response_payload": {"choices": [{"message": {"content": "raw"}}]},
    }

    redacted = redact_payload(payload, profile="local_default")

    assert redacted["id"] == "write_001"
    assert redacted["status"] == "accepted"
    assert redacted["authorization"] == REDACTED_AUTH_HEADER
    assert redacted["database_url"] == REDACTED_DATABASE_URL
    assert redacted["provider_config"] == REDACTED_PROVIDER_CONFIG
    assert redacted["messages"][0]["content"] == REDACTED_USER_TEXT
    assert redacted["memory"]["content"] == REDACTED_USER_TEXT
    assert redacted["memory"]["reason"] == REDACTED_REASON
    assert redacted["context"]["assembled_prompt"] == REDACTED_PROMPT
    assert redacted["context"]["raw_output"] == REDACTED_TRACE_PAYLOAD
    assert redacted["source_chunk"]["text"] == REDACTED_SOURCE_TEXT
    assert redacted["source_chunk"]["text_preview"] == "Short source preview."
    assert redacted["error"]["stack_trace"] == REDACTED_STACK_TRACE
    assert redacted["error"]["message"] == f"failed while opening {REDACTED_PATH}"
    assert redacted["provider_response_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert payload["memory"]["content"] == "User likes late-night writing."
    assert _serialized(redacted).find("sk-live-secret") == -1
    assert _serialized(redacted).find("C:\\Users\\figna") == -1


def test_redaction_recurses_through_pydantic_inspection_models() -> None:
    context = ContextPackageDetail(
        id="ctx_001",
        conversation_id="conv_001",
        interaction_mode=InteractionMode.REALITY_CHAT,
        persona_version_id="persona_001",
        memory_ids=["mem_001"],
        retrieved_chunk_ids=["chunk_001"],
        created_at=NOW,
        assembled_prompt="developer prompt and user message",
        memories=[
            MemorySummary(
                id="mem_001",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="User prefers writing after midnight.",
                importance=0.8,
                reason="User stated the preference.",
                created_at=NOW,
            )
        ],
        retrieved_chunks=[
            SourceChunkDetail(
                id="chunk_001",
                source_work_id="sw_001",
                paragraph_index=1,
                text_preview="Lin Shuang watches the room.",
                text="Full source chapter text.",
            )
        ],
    )

    redacted = redact_payload(context)

    assert redacted["assembled_prompt"] == REDACTED_PROMPT
    assert redacted["memories"][0]["content"] == REDACTED_USER_TEXT
    assert redacted["memories"][0]["reason"] == REDACTED_REASON
    assert redacted["retrieved_chunks"][0]["text"] == REDACTED_SOURCE_TEXT
    assert redacted["retrieved_chunks"][0]["text_preview"] == "Lin Shuang watches the room."


def test_local_debug_keeps_debug_text_but_never_leaks_secrets_paths_or_stacks() -> None:
    payload = {
        "api_key": "sk-debug-secret",
        "authorization": "Bearer debug-token",
        "assembled_prompt": "Prompt kept for local debugging.",
        "memory": {
            "scope": "user_memory",
            "status": "accepted",
            "importance": 0.7,
            "content": "User likes midnight writing.",
            "reason": "User stated it in chat.",
        },
        "source_chunk": {
            "source_work_id": "sw_001",
            "paragraph_index": 2,
            "text": "Full source text is visible in explicit local debug.",
        },
        "raw_output": "{\"text\":\"debug\",\"api_key\":\"sk-hidden-in-json\"}",
        "error_message": "provider opened /home/figna/private/config.toml",
        "traceback": "Traceback (most recent call last):\n  File \"/home/figna/app.py\"",
    }

    redacted = redact_payload(payload, profile="local_debug")

    assert redacted["api_key"] == REDACTED_SECRET
    assert redacted["authorization"] == REDACTED_AUTH_HEADER
    assert redacted["assembled_prompt"] == "Prompt kept for local debugging."
    assert redacted["memory"]["content"] == "User likes midnight writing."
    assert redacted["memory"]["reason"] == "User stated it in chat."
    assert (
        redacted["source_chunk"]["text"]
        == "Full source text is visible in explicit local debug."
    )
    assert redacted["raw_output"] == "{\"text\":\"debug\",\"api_key\":\"[redacted:secret]\"}"
    assert redacted["error_message"] == f"provider opened {REDACTED_PATH}"
    assert redacted["traceback"] == REDACTED_STACK_TRACE
    assert _serialized(redacted).find("sk-debug-secret") == -1
    assert _serialized(redacted).find("sk-hidden-in-json") == -1
    assert _serialized(redacted).find("/home/figna") == -1


def test_platform_default_is_more_restrictive_for_provider_labels_and_source_previews() -> None:
    payload = {
        "provider_name": "openai-compatible",
        "model_name": "private-deployment-model",
        "embedding_model": "private-embedding-model",
        "source_chunk": {
            "id": "chunk_001",
            "source_work_id": "sw_001",
            "paragraph_index": 1,
            "text_preview": "Preview text",
            "text": "Full source text",
        },
        "result": {
            "id": "mem_001",
            "status": "accepted",
            "content": "Broad platform content should not default to raw text.",
        },
    }

    redacted = redact_payload(payload, profile="platform_default")

    assert redacted["provider_name"] == REDACTED_PROVIDER_LABEL
    assert redacted["model_name"] == REDACTED_PROVIDER_LABEL
    assert redacted["embedding_model"] == REDACTED_PROVIDER_LABEL
    assert redacted["source_chunk"]["text_preview"] == REDACTED_SOURCE_TEXT
    assert redacted["source_chunk"]["text"] == REDACTED_SOURCE_TEXT
    assert redacted["result"]["id"] == "mem_001"
    assert redacted["result"]["status"] == "accepted"
    assert redacted["result"]["content"] == REDACTED_USER_TEXT


def _serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
