from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.critic.prompts import CRITIC_SYSTEM_PROMPT, build_critic_user_prompt
from personality_jelly.critic.schemas import CriticEvaluation
from personality_jelly.domain import CriticReport, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder, record_structured_output
from personality_jelly.storage import (
    ContextPackageRepository,
    CriticReportRepository,
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
)


CRITIC_EVALUATION_OPERATION = "critic.evaluate_message"


@dataclass(frozen=True)
class CriticEvaluationResult:
    critic_report: CriticReport


def evaluate_message(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    message_id: str,
) -> CriticEvaluationResult:
    message_repository = MessageRepository(session)
    assistant_message = message_repository.require(message_id)
    if assistant_message.role != MessageRole.ASSISTANT:
        raise ValueError("Critic can only evaluate assistant messages")
    if assistant_message.context_package_id is None:
        raise ValueError("Assistant message has no context_package_id")

    context_package = ContextPackageRepository(session).require(assistant_message.context_package_id)
    persona = PersonaVersionRepository(session).require(context_package.persona_version_id)
    user_message = _previous_user_message(
        message_repository.list_by_conversation(assistant_message.conversation_id),
        assistant_message.id,
    )

    schema = CriticEvaluation.model_json_schema()
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=CRITIC_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_critic_user_prompt(
                    persona=persona,
                    context_package=context_package,
                    user_message=user_message,
                    assistant_message=assistant_message,
                ),
            ),
        ],
        schema=schema,
        model_config=model_config,
    )
    trace_recorder = RepositoryLLMTraceRecorder(LLMRawOutputRepository(session))
    try:
        evaluation = TypeAdapter(CriticEvaluation).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=CRITIC_EVALUATION_OPERATION,
            schema_name=CriticEvaluation.__name__,
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=CRITIC_EVALUATION_OPERATION,
        schema_name=CriticEvaluation.__name__,
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=evaluation,
    )
    critic_report = CriticReport(
        id=generate_id(EntityKind.CRITIC_REPORT),
        message_id=assistant_message.id,
        ooc_risk=evaluation.ooc_risk,
        fact_risk=evaluation.fact_risk,
        memory_risk=evaluation.memory_risk,
        mode_risk=evaluation.mode_risk,
        reasons=evaluation.reasons,
        suggested_action=evaluation.suggested_action,
    )
    CriticReportRepository(session).add(critic_report)
    return CriticEvaluationResult(critic_report=critic_report)


def _previous_user_message(messages, assistant_message_id: str):
    previous = []
    for message in messages:
        if message.id == assistant_message_id:
            break
        previous.append(message)
    for message in reversed(previous):
        if message.role == MessageRole.USER:
            return message
    return None

