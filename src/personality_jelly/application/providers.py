from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from personality_jelly.core import Settings
from personality_jelly.llm import (
    EmbeddingConfig,
    LLMProvider,
    ModelConfig,
    build_embedding_provider,
    build_llm_provider,
)
from personality_jelly.runtime import RoleplayTurnModelConfigs, RoleplayTurnProviders


ProviderFactory = Callable[[Settings], LLMProvider]
StubProviderFactory = Callable[[], LLMProvider]


@dataclass(frozen=True)
class ProviderRoleBundle:
    roleplay: LLMProvider
    critic: LLMProvider | None = None
    memory_curator: LLMProvider | None = None
    mode_classifier: LLMProvider | None = None
    retriever: LLMProvider | None = None

    def to_runtime_turn_providers(self) -> RoleplayTurnProviders:
        return RoleplayTurnProviders(
            roleplay=self.roleplay,
            critic=self.critic,
            memory_curator=self.memory_curator,
            mode_classifier=self.mode_classifier,
            retriever=self.retriever,
        )


@dataclass(frozen=True)
class ModelRoleBundle:
    roleplay: ModelConfig
    critic: ModelConfig | None = None
    memory_curator: ModelConfig | None = None
    mode_classifier: ModelConfig | None = None
    retrieval_embedding: EmbeddingConfig | None = None

    def to_runtime_turn_model_configs(self) -> RoleplayTurnModelConfigs:
        return RoleplayTurnModelConfigs(
            roleplay=self.roleplay,
            critic=self.critic,
            memory_curator=self.memory_curator,
            mode_classifier=self.mode_classifier,
            retrieval_embedding=self.retrieval_embedding,
        )


def build_turn_role_bundles(
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    retriever: LLMProvider | None = None,
    retrieval_embedding: EmbeddingConfig | None = None,
) -> tuple[ProviderRoleBundle, ModelRoleBundle]:
    return (
        ProviderRoleBundle(
            roleplay=provider,
            critic=provider,
            memory_curator=provider,
            mode_classifier=provider,
            retriever=retriever,
        ),
        ModelRoleBundle(
            roleplay=model_config,
            critic=model_config,
            memory_curator=model_config,
            mode_classifier=model_config,
            retrieval_embedding=retrieval_embedding,
        ),
    )


def resolve_embedding_config(settings: Settings) -> EmbeddingConfig | None:
    embedding_model = settings.embedding_model.strip() if settings.embedding_model else ""
    if not embedding_model:
        return None
    return EmbeddingConfig(model=embedding_model)


def resolve_embedding_provider(
    provider_source: str,
    *,
    settings: Settings,
    stub_provider_factory: StubProviderFactory,
    embedding_provider_factory: ProviderFactory = build_embedding_provider,
) -> tuple[LLMProvider | None, EmbeddingConfig | None]:
    embedding_config = resolve_embedding_config(settings)
    if embedding_config is None:
        return None, None
    if provider_source == "stub":
        return stub_provider_factory(), embedding_config
    if provider_source == "env":
        return embedding_provider_factory(settings), embedding_config
    raise ValueError(f"unsupported provider source {provider_source!r}")


def resolve_roleplay_provider(
    provider_source: str,
    *,
    settings: Settings,
    stub_provider_factory: StubProviderFactory,
    llm_provider_factory: ProviderFactory = build_llm_provider,
) -> tuple[LLMProvider, ModelConfig]:
    if provider_source == "stub":
        return stub_provider_factory(), ModelConfig(model="stub")

    if provider_source == "env":
        llm_model = settings.llm_model.strip() if settings.llm_model else ""
        if not llm_model:
            raise ValueError("PJ_LLM_MODEL is required when using --provider env")
        return llm_provider_factory(settings), ModelConfig(model=llm_model)

    raise ValueError(f"unsupported provider source {provider_source!r}")
