from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import ContextPackage, InteractionMode, Message, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.runtime.context import build_context_package
from personality_jelly.storage import MessageRepository


@dataclass(frozen=True)
class RoleplayTurnResult:
    user_message: Message
    assistant_message: Message
    context_package: ContextPackage


def send_message(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    conversation_id: str,
    content: str,
    interaction_mode: InteractionMode | None = None,
) -> RoleplayTurnResult:
    user_message = Message(
        id=generate_id(EntityKind.MESSAGE),
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=content,
    )
    MessageRepository(session).add(user_message)

    context_package = build_context_package(
        session,
        conversation_id=conversation_id,
        user_message=content,
        interaction_mode=interaction_mode,
    ).context_package
    assistant_text = provider.generate_text(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=context_package.assembled_prompt),
            ChatMessage(role=MessageRole.USER, content=content),
        ],
        model_config=model_config,
    )
    assistant_message = Message(
        id=generate_id(EntityKind.MESSAGE),
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_text,
        context_package_id=context_package.id,
    )
    MessageRepository(session).add(assistant_message)

    return RoleplayTurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        context_package=context_package,
    )

