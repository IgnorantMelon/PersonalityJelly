from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    ClaimStatus,
    ContextPackage,
    InteractionMode,
    MemoryStatus,
)
from personality_jelly.runtime.mode import resolve_interaction_mode
from personality_jelly.storage import (
    CanonClaimRepository,
    ContextPackageRepository,
    ConversationRepository,
    MemoryRepository,
    PersonaVersionRepository,
)


@dataclass(frozen=True)
class ContextBuildResult:
    context_package: ContextPackage


def build_context_package(
    session: Session,
    *,
    conversation_id: str,
    user_message: str,
    interaction_mode: InteractionMode | None = None,
) -> ContextBuildResult:
    conversation = ConversationRepository(session).require(conversation_id)
    mode = resolve_interaction_mode(
        user_message,
        explicit_mode=interaction_mode,
        current_mode=conversation.current_mode,
    )
    persona = PersonaVersionRepository(session).require(conversation.persona_version_id)
    claims = CanonClaimRepository(session).list_by_character(
        conversation.character_id,
        status=ClaimStatus.VERIFIED,
    )
    memories = MemoryRepository(session).list_for_user_character(
        conversation.user_id,
        conversation.character_id,
        status=MemoryStatus.ACCEPTED,
    )

    context_package = ContextPackage(
        id=generate_id(EntityKind.CONTEXT_PACKAGE),
        conversation_id=conversation.id,
        interaction_mode=mode,
        persona_version_id=persona.id,
        claim_ids=[claim.id for claim in claims],
        memory_ids=[memory.id for memory in memories],
        retrieved_chunk_ids=[],
        assembled_prompt=_assemble_prompt(
            user_message=user_message,
            interaction_mode=mode,
            persona_core_self=persona.core_self,
            speech_rules=persona.speech_rules,
            behavior_rules=persona.behavior_rules,
            world_adaptation_rules=persona.world_adaptation_rules,
            forbidden_rules=persona.forbidden_rules,
            claim_contents=[claim.content for claim in claims],
            memory_contents=[memory.content for memory in memories],
            conversation_summary=conversation.summary,
        ),
    )
    ContextPackageRepository(session).add(context_package)
    return ContextBuildResult(context_package=context_package)


def _assemble_prompt(
    *,
    user_message: str,
    interaction_mode: InteractionMode | str,
    persona_core_self: str,
    speech_rules: list[str],
    behavior_rules: list[str],
    world_adaptation_rules: list[str],
    forbidden_rules: list[str],
    claim_contents: list[str],
    memory_contents: list[str],
    conversation_summary: str | None,
) -> str:
    sections = [
        "# Safety and Boundary Rules",
        "- Preserve canon. Do not let user conversation rewrite original facts.",
        "- Keep user memories separate from canon.",
        "",
        "# Interaction Mode",
        str(interaction_mode),
        "",
        "# Persona Core Self",
        persona_core_self,
        "",
        "# Speech Rules",
        _format_items(speech_rules),
        "",
        "# Behavior Rules",
        _format_items(behavior_rules),
        "",
        "# Reality Adaptation Rules",
        _format_items(world_adaptation_rules),
        "",
        "# Forbidden Rules",
        _format_items(forbidden_rules),
        "",
        "# Verified Canon Claims",
        _format_items(claim_contents),
        "",
        "# Accepted User/Relationship Memories",
        _format_items(memory_contents),
        "",
        "# Conversation Summary",
        conversation_summary or "none",
        "",
        "# Current User Message",
        user_message,
    ]
    return "\n".join(sections)


def _format_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"

