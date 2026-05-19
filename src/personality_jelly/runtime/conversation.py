from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import Conversation, InteractionMode, User
from personality_jelly.storage import (
    CharacterRepository,
    ConversationRepository,
    PersonaVersionRepository,
    UserRepository,
)


@dataclass(frozen=True)
class UserCreationResult:
    user: User


@dataclass(frozen=True)
class ConversationCreationResult:
    conversation: Conversation


def create_user(
    session: Session,
    *,
    display_name: str | None = None,
    user_id: str | None = None,
) -> UserCreationResult:
    user = User(
        id=user_id or generate_id(EntityKind.USER),
        display_name=display_name,
    )
    UserRepository(session).add(user)
    return UserCreationResult(user=user)


def create_conversation(
    session: Session,
    *,
    user_id: str,
    character_id: str,
    persona_version_id: str | None = None,
    interaction_mode: InteractionMode = InteractionMode.REALITY_CHAT,
    conversation_id: str | None = None,
) -> ConversationCreationResult:
    UserRepository(session).require(user_id)
    CharacterRepository(session).require(character_id)
    persona_repository = PersonaVersionRepository(session)
    persona = (
        persona_repository.require(persona_version_id)
        if persona_version_id is not None
        else persona_repository.latest_for_character(character_id)
    )
    if persona is None:
        raise ValueError(f"Character {character_id!r} has no persona version")
    if persona.character_id != character_id:
        raise ValueError(
            f"Persona version {persona.id!r} does not belong to character {character_id!r}"
        )

    conversation = Conversation(
        id=conversation_id or generate_id(EntityKind.CONVERSATION),
        user_id=user_id,
        character_id=character_id,
        persona_version_id=persona.id,
        current_mode=interaction_mode,
    )
    ConversationRepository(session).add(conversation)
    return ConversationCreationResult(conversation=conversation)

