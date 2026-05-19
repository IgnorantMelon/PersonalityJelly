from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import ClaimStatus, MessageRole, PersonaVersion
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.persona.prompts import COMPILER_SYSTEM_PROMPT, build_compiler_user_prompt
from personality_jelly.persona.schemas import PersonaCompilation
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    PersonaVersionRepository,
)


@dataclass(frozen=True)
class PersonaCompilationResult:
    persona_version: PersonaVersion


def compile_persona_version(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    character_id: str,
) -> PersonaCompilationResult:
    character = CharacterRepository(session).require(character_id)
    verified_claims = CanonClaimRepository(session).list_by_character(
        character_id,
        status=ClaimStatus.VERIFIED,
    )
    if not verified_claims:
        raise ValueError(f"Character {character_id!r} has no verified claims to compile")

    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=COMPILER_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_compiler_user_prompt(
                    character=character,
                    claims=verified_claims,
                ),
            ),
        ],
        schema=PersonaCompilation.model_json_schema(),
        model_config=model_config,
    )
    compiled = TypeAdapter(PersonaCompilation).validate_python(raw)

    repository = PersonaVersionRepository(session)
    persona_version = PersonaVersion(
        id=generate_id(EntityKind.PERSONA_VERSION),
        character_id=character.id,
        source_work_id=character.source_work_id,
        version_number=repository.next_version_number(character.id),
        core_self=compiled.core_self,
        speech_rules=compiled.speech_rules,
        behavior_rules=compiled.behavior_rules,
        world_adaptation_rules=compiled.world_adaptation_rules,
        forbidden_rules=compiled.forbidden_rules,
        source_claim_ids=[claim.id for claim in verified_claims],
    )
    repository.add(persona_version)
    return PersonaCompilationResult(persona_version=persona_version)

