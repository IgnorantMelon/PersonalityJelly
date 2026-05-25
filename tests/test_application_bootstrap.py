from __future__ import annotations

import pytest

from personality_jelly.application import (
    build_turn_role_bundles,
    normalize_error,
    resolve_database_url,
    resolve_embedding_config,
    resolve_embedding_provider,
    resolve_roleplay_provider,
)
from personality_jelly.core import Settings
from personality_jelly.llm import EmbeddingConfig, ModelConfig
from personality_jelly.testing.stub_provider import StubProvider


class RecordingProvider(StubProvider):
    pass


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_resolve_database_url_preserves_cli_memory_db_rule() -> None:
    settings = _settings(database_url="sqlite:///configured.db")

    assert resolve_database_url(settings=settings) == "sqlite:///configured.db"
    assert resolve_database_url(settings=settings, database_url="sqlite:///explicit.db") == (
        "sqlite:///explicit.db"
    )
    assert resolve_database_url(settings=settings, memory_db=True) == "sqlite:///:memory:"

    with pytest.raises(ValueError, match="--memory-db cannot be combined with --database-url"):
        resolve_database_url(
            settings=settings,
            database_url="sqlite:///explicit.db",
            memory_db=True,
        )


def test_resolve_roleplay_provider_uses_stub_or_env_model() -> None:
    stub_provider, stub_config = resolve_roleplay_provider(
        "stub",
        settings=_settings(),
        stub_provider_factory=RecordingProvider,
    )

    assert isinstance(stub_provider, RecordingProvider)
    assert stub_config == ModelConfig(model="stub")

    env_provider = RecordingProvider()
    resolved_provider, resolved_config = resolve_roleplay_provider(
        "env",
        settings=_settings(llm_model="chat-model"),
        stub_provider_factory=RecordingProvider,
        llm_provider_factory=lambda settings: env_provider,
    )

    assert resolved_provider is env_provider
    assert resolved_config == ModelConfig(model="chat-model")


def test_resolve_roleplay_provider_requires_env_model() -> None:
    with pytest.raises(ValueError, match="PJ_LLM_MODEL is required"):
        resolve_roleplay_provider(
            "env",
            settings=_settings(llm_model=""),
            stub_provider_factory=RecordingProvider,
            llm_provider_factory=lambda settings: RecordingProvider(),
        )


def test_resolve_embedding_provider_returns_optional_retriever() -> None:
    settings = _settings(embedding_model="embedding-model")
    provider, config = resolve_embedding_provider(
        "stub",
        settings=settings,
        stub_provider_factory=RecordingProvider,
    )

    assert isinstance(provider, RecordingProvider)
    assert config == EmbeddingConfig(model="embedding-model")
    assert resolve_embedding_config(_settings(embedding_model="")) is None
    assert resolve_embedding_provider(
        "stub",
        settings=_settings(embedding_model=""),
        stub_provider_factory=RecordingProvider,
    ) == (None, None)


def test_turn_role_bundles_convert_to_runtime_configs() -> None:
    provider = RecordingProvider()
    retriever = RecordingProvider()
    providers, model_configs = build_turn_role_bundles(
        provider=provider,
        model_config=ModelConfig(model="chat-model"),
        retriever=retriever,
        retrieval_embedding=EmbeddingConfig(model="embedding-model"),
    )

    runtime_providers = providers.to_runtime_turn_providers()
    runtime_configs = model_configs.to_runtime_turn_model_configs()

    assert runtime_providers.roleplay is provider
    assert runtime_providers.critic is provider
    assert runtime_providers.memory_curator is provider
    assert runtime_providers.mode_classifier is provider
    assert runtime_providers.retriever is retriever
    assert runtime_configs.roleplay == ModelConfig(model="chat-model")
    assert runtime_configs.retrieval_embedding == EmbeddingConfig(model="embedding-model")


def test_normalize_error_maps_common_application_errors() -> None:
    missing = normalize_error(LookupError("missing row"))
    invalid = normalize_error(ValueError("bad input"))
    unexpected = normalize_error(RuntimeError("boom"))

    assert missing.code == "not_found"
    assert invalid.code == "validation_error"
    assert unexpected.code == "unexpected_error"
    assert unexpected.details["exception_type"] == "RuntimeError"
