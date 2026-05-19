from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.critic import evaluate_message
from personality_jelly.domain import CriticReport, InteractionMode, Memory, Message
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.memory import curate_memories_for_message
from personality_jelly.runtime.roleplay import send_message


@dataclass(frozen=True)
class RoleplayTurnProviders:
    roleplay: LLMProvider
    critic: LLMProvider | None = None
    memory_curator: LLMProvider | None = None


@dataclass(frozen=True)
class RoleplayTurnModelConfigs:
    roleplay: ModelConfig
    critic: ModelConfig | None = None
    memory_curator: ModelConfig | None = None


@dataclass(frozen=True)
class RoleplayTurnOrchestrationResult:
    user_message: Message
    assistant_message: Message
    critic_report: CriticReport | None
    memories: list[Memory]


def send_roleplay_turn(
    session: Session,
    *,
    conversation_id: str,
    content: str,
    providers: RoleplayTurnProviders,
    model_configs: RoleplayTurnModelConfigs,
    interaction_mode: InteractionMode | None = None,
) -> RoleplayTurnOrchestrationResult:
    turn = send_message(
        session,
        provider=providers.roleplay,
        model_config=model_configs.roleplay,
        conversation_id=conversation_id,
        content=content,
        interaction_mode=interaction_mode,
    )

    critic_report = None
    if providers.critic is not None:
        if model_configs.critic is None:
            raise ValueError("critic model config is required when critic provider is supplied")
        critic_report = evaluate_message(
            session,
            provider=providers.critic,
            model_config=model_configs.critic,
            message_id=turn.assistant_message.id,
        ).critic_report

    memories: list[Memory] = []
    if providers.memory_curator is not None:
        if model_configs.memory_curator is None:
            raise ValueError(
                "memory curator model config is required when memory curator provider is supplied"
            )
        memories = curate_memories_for_message(
            session,
            provider=providers.memory_curator,
            model_config=model_configs.memory_curator,
            message_id=turn.assistant_message.id,
            critic_report_id=critic_report.id if critic_report is not None else None,
        ).memories

    return RoleplayTurnOrchestrationResult(
        user_message=turn.user_message,
        assistant_message=turn.assistant_message,
        critic_report=critic_report,
        memories=memories,
    )

