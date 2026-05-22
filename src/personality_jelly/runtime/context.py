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
from personality_jelly.llm import EmbeddingConfig, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.retrieval import retrieve_source_chunks
from personality_jelly.runtime.mode import resolve_interaction_mode
from personality_jelly.runtime.summary import parse_layered_summary
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ContextPackageRepository,
    ConversationRepository,
    LLMRawOutputRepository,
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
    mode_provider: LLMProvider | None = None,
    mode_model_config: ModelConfig | None = None,
    retrieval_provider: LLMProvider | None = None,
    embedding_config: EmbeddingConfig | None = None,
) -> ContextBuildResult:
    conversation = ConversationRepository(session).require(conversation_id)
    mode = resolve_interaction_mode(
        user_message,
        explicit_mode=interaction_mode,
        current_mode=conversation.current_mode,
        provider=mode_provider,
        model_config=mode_model_config,
        trace_recorder=RepositoryLLMTraceRecorder(LLMRawOutputRepository(session)),
    )
    persona = PersonaVersionRepository(session).require(conversation.persona_version_id)
    character = CharacterRepository(session).require(conversation.character_id)
    claims = CanonClaimRepository(session).list_by_character(
        conversation.character_id,
        status=ClaimStatus.VERIFIED,
    )
    memories = MemoryRepository(session).list_for_user_character(
        conversation.user_id,
        conversation.character_id,
        status=MemoryStatus.ACCEPTED,
    )
    retrieval = retrieve_source_chunks(
        session,
        source_work_id=character.source_work_id,
        character=character,
        query=user_message,
        provider=retrieval_provider,
        embedding_config=embedding_config,
    )

    context_package = ContextPackage(
        id=generate_id(EntityKind.CONTEXT_PACKAGE),
        conversation_id=conversation.id,
        interaction_mode=mode,
        persona_version_id=persona.id,
        claim_ids=[claim.id for claim in claims],
        memory_ids=[memory.id for memory in memories],
        retrieved_chunk_ids=[chunk.id for chunk in retrieval.chunks],
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
            retrieved_chunks=[
                _format_retrieved_chunk(chunk)
                for chunk in retrieval.chunks
            ],
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
    retrieved_chunks: list[str],
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
        "# Retrieved Source Chunks",
        _format_items(retrieved_chunks),
        "",
        "# Conversation Summary",
        _format_conversation_summary(conversation_summary),
        "",
        "# Current User Message",
        user_message,
    ]
    return "\n".join(sections)


def _format_conversation_summary(summary: str | None) -> str:
    layers = parse_layered_summary(summary)
    return "\n".join(
        [
            "## short_term_scene_state",
            layers.short_term_scene_state or "none",
            "",
            "## user_memory_candidates",
            _format_items(layers.user_memory_candidates),
            "",
            "## relationship_memory_notes",
            _format_items(layers.relationship_memory_notes),
            "",
            "## reflective_notes",
            _format_items(layers.reflective_notes),
        ]
    )


def _format_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def _format_retrieved_chunk(chunk) -> str:
    location = f"chapter={chunk.chapter_index}, paragraph={chunk.paragraph_index}"
    return f"{chunk.id} ({location}): {chunk.text}"

