from __future__ import annotations

from personality_jelly.core.settings import Settings
from personality_jelly.llm.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAIJSONResponseFormat,
    OpenAICompatibleProvider,
)
from personality_jelly.llm.provider import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    provider_name = (settings.llm_provider or "").strip().lower()
    if provider_name in {"openai-compatible", "openai_compatible", "openai"}:
        if not settings.llm_api_key:
            raise ValueError("PJ_LLM_API_KEY is required for the openai-compatible provider")
        return OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                timeout_seconds=settings.llm_timeout_seconds,
                json_response_format=_json_response_format(
                    settings.llm_json_response_format,
                ),
            )
        )
    if not provider_name:
        raise ValueError("PJ_LLM_PROVIDER is not configured")
    raise ValueError(f"Unsupported LLM provider {settings.llm_provider!r}")


def build_embedding_provider(settings: Settings) -> LLMProvider:
    provider_name = (
        settings.embedding_provider or settings.llm_provider or ""
    ).strip().lower()
    if provider_name in {"openai-compatible", "openai_compatible", "openai"}:
        api_key = settings.embedding_api_key or settings.llm_api_key
        if not api_key:
            raise ValueError("PJ_EMBEDDING_API_KEY is required for the embedding provider")
        return OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url=settings.embedding_base_url or settings.llm_base_url,
                api_key=api_key,
                timeout_seconds=settings.embedding_timeout_seconds
                or settings.llm_timeout_seconds,
                json_response_format=_json_response_format(
                    settings.llm_json_response_format,
                ),
            )
        )
    if not provider_name:
        raise ValueError("PJ_EMBEDDING_PROVIDER or PJ_LLM_PROVIDER is not configured")
    raise ValueError(f"Unsupported embedding provider {provider_name!r}")


def _json_response_format(value: str) -> OpenAIJSONResponseFormat:
    normalized = value.strip().lower()
    try:
        return OpenAIJSONResponseFormat(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in OpenAIJSONResponseFormat)
        raise ValueError(
            f"Unsupported PJ_LLM_JSON_RESPONSE_FORMAT {value!r}; expected one of: {allowed}"
        ) from exc
