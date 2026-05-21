from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from personality_jelly.domain import Conversation, MessageRole
from personality_jelly.domain.models import utc_now
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.runtime.summary_prompts import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)
from personality_jelly.runtime.summary_schemas import ConversationSummaryDraft
from personality_jelly.storage import ConversationRepository, MessageRepository


@dataclass(frozen=True)
class ConversationSummaryResult:
    conversation: Conversation


def summarize_conversation(
    session: Session,
    *,
    conversation_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    max_messages: int = 20,
) -> ConversationSummaryResult:
    if max_messages < 1:
        raise ValueError("max_messages must be greater than 0")

    conversation_repository = ConversationRepository(session)
    conversation = conversation_repository.require(conversation_id)
    messages = MessageRepository(session).list_by_conversation(conversation.id)
    recent_messages = messages[-max_messages:]
    if not recent_messages:
        raise ValueError(f"Conversation {conversation_id!r} has no messages to summarize")

    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=SUMMARY_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_summary_user_prompt(
                    conversation=conversation,
                    messages=recent_messages,
                ),
            ),
        ],
        schema=ConversationSummaryDraft.model_json_schema(),
        model_config=model_config,
    )
    draft = TypeAdapter(ConversationSummaryDraft).validate_python(raw)
    updated = conversation_repository.update_summary(
        conversation.id,
        summary=_format_layered_summary(draft),
        updated_at=utc_now(),
    )
    return ConversationSummaryResult(conversation=updated)


def _format_layered_summary(draft: ConversationSummaryDraft) -> str:
    return "\n".join(
        [
            "# Short-term Scene State",
            draft.short_term_scene_state,
            "",
            "# User Memory Candidates",
            _format_items(draft.user_memory_candidates),
            "",
            "# Relationship Memory Notes",
            _format_items(draft.relationship_memory_notes),
            "",
            "# Reflective Notes",
            _format_items(draft.reflective_notes),
        ]
    )


def _format_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"
