from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from personality_jelly.critic import evaluate_message
from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    ContextPackage,
    CriticReport,
    FailureCase,
    InteractionMode,
    Memory,
    Message,
)
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.memory import curate_memories_for_message
from personality_jelly.runtime.roleplay import send_message
from personality_jelly.storage import FailureCaseRepository


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
    context_package: ContextPackage
    critic_report: CriticReport | None
    memories: list[Memory]
    retry_count: int = 0
    rejected_assistant_message: Message | None = None
    rejected_critic_report: CriticReport | None = None
    failure_cases: list[FailureCase] = field(default_factory=list)


def send_roleplay_turn(
    session: Session,
    *,
    conversation_id: str,
    content: str,
    providers: RoleplayTurnProviders,
    model_configs: RoleplayTurnModelConfigs,
    interaction_mode: InteractionMode | None = None,
    retry_on_critic: bool = False,
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

    retry_count = 0
    rejected_assistant_message = None
    rejected_critic_report = None
    failure_cases: list[FailureCase] = []
    final_retry_recorded = False
    if _critic_requests_retry(critic_report):
        if retry_on_critic:
            retry_count = 1
            rejected_assistant_message = turn.assistant_message
            rejected_critic_report = critic_report
            failure_cases.append(
                _record_failure_case(
                    session,
                    user_message=turn.user_message,
                    assistant_message=turn.assistant_message,
                    context_package=turn.context_package,
                    critic_report=critic_report,
                    notes="Captured rejected assistant response before retry.",
                )
            )
            turn = send_message(
                session,
                provider=providers.roleplay,
                model_config=model_configs.roleplay,
                conversation_id=conversation_id,
                content=content,
                interaction_mode=interaction_mode,
                persist_user_message=False,
            )
            critic_report = None
            if providers.critic is not None:
                if model_configs.critic is None:
                    raise ValueError(
                        "critic model config is required when critic provider is supplied"
                    )
                critic_report = evaluate_message(
                    session,
                    provider=providers.critic,
                    model_config=model_configs.critic,
                    message_id=turn.assistant_message.id,
                ).critic_report
        else:
            final_retry_recorded = True
            failure_cases.append(
                _record_failure_case(
                    session,
                    user_message=turn.user_message,
                    assistant_message=turn.assistant_message,
                    context_package=turn.context_package,
                    critic_report=critic_report,
                    notes="Captured assistant response flagged for retry.",
                )
            )

    if _critic_requests_retry(critic_report) and not final_retry_recorded:
        failure_cases.append(
            _record_failure_case(
                session,
                user_message=turn.user_message,
                assistant_message=turn.assistant_message,
                context_package=turn.context_package,
                critic_report=critic_report,
                notes="Captured assistant response flagged for retry.",
            )
        )

    if _critic_requests_log(critic_report):
        failure_cases.append(
            _record_failure_case(
                session,
                user_message=turn.user_message,
                assistant_message=turn.assistant_message,
                context_package=turn.context_package,
                critic_report=critic_report,
                notes="Captured assistant response flagged for review.",
            )
        )

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
        context_package=turn.context_package,
        critic_report=critic_report,
        memories=memories,
        retry_count=retry_count,
        rejected_assistant_message=rejected_assistant_message,
        rejected_critic_report=rejected_critic_report,
        failure_cases=failure_cases,
    )


def _critic_requests_retry(critic_report: CriticReport | None) -> bool:
    return critic_report is not None and critic_report.suggested_action == "retry"


def _critic_requests_log(critic_report: CriticReport | None) -> bool:
    return critic_report is not None and critic_report.suggested_action == "log"


def _record_failure_case(
    session: Session,
    *,
    user_message: Message,
    assistant_message: Message,
    context_package: ContextPackage,
    critic_report: CriticReport,
    notes: str,
) -> FailureCase:
    failure_case = FailureCase(
        id=generate_id(EntityKind.FAILURE_CASE),
        conversation_id=assistant_message.conversation_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        context_package_id=context_package.id,
        critic_report_id=critic_report.id,
        category=critic_report.suggested_action,
        reason=_failure_reason(critic_report),
        notes=notes,
    )
    FailureCaseRepository(session).add(failure_case)
    return failure_case


def _failure_reason(critic_report: CriticReport) -> str:
    if critic_report.reasons:
        return "; ".join(critic_report.reasons)
    return f"Critic suggested {critic_report.suggested_action}."

