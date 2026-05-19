from __future__ import annotations

from personality_jelly.core.settings import Settings
from personality_jelly.llm.openai_compatible import (
    OpenAICompatibleConfig,
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
            )
        )
    if not provider_name:
        raise ValueError("PJ_LLM_PROVIDER is not configured")
    raise ValueError(f"Unsupported LLM provider {settings.llm_provider!r}")
