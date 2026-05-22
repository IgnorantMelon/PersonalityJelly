from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import Memory, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder, record_structured_output
from personality_jelly.memory.guard import guard_memory_candidates
from personality_jelly.memory.prompts import CURATOR_SYSTEM_PROMPT, build_curator_user_prompt
from personality_jelly.memory.schemas import MemoryCuration
from personality_jelly.runtime.summary import parse_layered_summary
from personality_jelly.storage import (
    ConversationRepository,
    ContextPackageRepository,
    CriticReportRepository,
    LLMRawOutputRepository,
    MemoryRepository,
    MessageRepository,
)


MEMORY_CURATOR_OPERATION = "memory.curator.extract_candidates"


@dataclass(frozen=True)
class MemoryCurationResult:
    memories: list[Memory]


def curate_memories_for_message(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    message_id: str,
    critic_report_id: str | None = None,
    guard_provider: LLMProvider | None = None,
    guard_model_config: ModelConfig | None = None,
) -> MemoryCurationResult:
    message_repository = MessageRepository(session)
    assistant_message = message_repository.require(message_id)
    if assistant_message.role != MessageRole.ASSISTANT:
        raise ValueError("Memory Curator expects an assistant message")
    if assistant_message.context_package_id is None:
        raise ValueError("Assistant message has no context_package_id")

    context_package = ContextPackageRepository(session).require(assistant_message.context_package_id)
    conversation = ConversationRepository(session).require(assistant_message.conversation_id)
    summary_layers = parse_layered_summary(conversation.summary)
    user_message = _previous_user_message(
        message_repository.list_by_conversation(assistant_message.conversation_id),
        assistant_message.id,
    )
    if user_message is None:
        raise ValueError("Could not find a previous user message for the assistant response")

    critic_report = (
        CriticReportRepository(session).require(critic_report_id)
        if critic_report_id is not None
        else None
    )

    schema = MemoryCuration.model_json_schema()
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=CURATOR_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_curator_user_prompt(
                    context_package=context_package,
                    summary_short_term_scene_state=summary_layers.short_term_scene_state,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    critic_report=critic_report,
                ),
            ),
        ],
        schema=schema,
        model_config=model_config,
    )
    trace_recorder = RepositoryLLMTraceRecorder(LLMRawOutputRepository(session))
    try:
        curation = TypeAdapter(MemoryCuration).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=MEMORY_CURATOR_OPERATION,
            schema_name=MemoryCuration.__name__,
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=MEMORY_CURATOR_OPERATION,
        schema_name=MemoryCuration.__name__,
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=curation,
    )
    guarded_candidates = guard_memory_candidates(
        curation.memories,
        user_message=user_message,
        assistant_message=assistant_message,
        interaction_mode=context_package.interaction_mode,
        critic_report=critic_report,
        provider=guard_provider or provider,
        model_config=guard_model_config or model_config,
        trace_recorder=trace_recorder,
    )

    memories = [
        Memory(
            id=generate_id(EntityKind.MEMORY),
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            conversation_id=assistant_message.conversation_id,
            scope=guarded.candidate.scope,
            status=guarded.candidate.status,
            content=guarded.candidate.content,
            importance=guarded.candidate.importance,
            reason=guarded.candidate.reason,
        )
        for guarded in guarded_candidates
    ]
    repository = MemoryRepository(session)
    for memory in memories:
        repository.add(memory)
    return MemoryCurationResult(memories=memories)


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
