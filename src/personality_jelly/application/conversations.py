from __future__ import annotations

from sqlalchemy.orm import Session

from personality_jelly.application.conversation_inspection import (
    ConversationInspectionOptions,
    inspect_conversation,
)
from personality_jelly.application.inspection import ConversationDetail
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.runtime import summarize_conversation


def summarize_conversation_workflow(
    session: Session,
    *,
    conversation_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    max_messages: int = 20,
    inspection_options: ConversationInspectionOptions | None = None,
) -> ConversationDetail:
    summarize_conversation(
        session,
        conversation_id=conversation_id,
        provider=provider,
        model_config=model_config,
        max_messages=max_messages,
    )
    return inspect_conversation(
        session,
        conversation_id,
        options=inspection_options
        or ConversationInspectionOptions(message_limit=max_messages),
    )
