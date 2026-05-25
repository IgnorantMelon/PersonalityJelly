from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.domain import Character, ClaimStatus, PersonaVersion, SourceWork
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import CharacterRepository, SourceWorkRepository


@dataclass(frozen=True)
class CharacterPersonaSetupResult:
    source_work: SourceWork
    character: Character
    candidate_claim_ids: list[str]
    evidence_ref_ids: list[str]
    verified_claim_ids: list[str]
    conflict_ids: list[str]
    persona_version: PersonaVersion

    @property
    def source_work_id(self) -> str:
        return self.source_work.id

    @property
    def character_id(self) -> str:
        return self.character.id

    @property
    def persona_version_id(self) -> str:
        return self.persona_version.id


def build_character_persona(
    session: Session,
    *,
    source_work_id: str,
    character_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    max_chunks: int | None = None,
) -> CharacterPersonaSetupResult:
    source_work = SourceWorkRepository(session).require(source_work_id)
    character = CharacterRepository(session).require(character_id)
    if character.source_work_id != source_work.id:
        raise ValueError(
            f"Character {character.id!r} does not belong to source work {source_work.id!r}"
        )

    extraction = run_reader_extraction(
        session,
        provider=provider,
        model_config=model_config,
        character_id=character.id,
        max_chunks=max_chunks,
    )
    verification = verify_candidate_claims(
        session,
        provider=provider,
        model_config=model_config,
        character=CharacterRepository(session).require(character.id),
    )
    compilation = compile_persona_version(
        session,
        provider=provider,
        model_config=model_config,
        character_id=character.id,
    )

    return CharacterPersonaSetupResult(
        source_work=source_work,
        character=character,
        candidate_claim_ids=[claim.id for claim in extraction.claims],
        evidence_ref_ids=[evidence.id for evidence in extraction.evidence_refs],
        verified_claim_ids=[
            claim.id
            for claim in verification.updated_claims
            if claim.status == ClaimStatus.VERIFIED
        ],
        conflict_ids=[conflict.id for conflict in verification.conflicts],
        persona_version=compilation.persona_version,
    )
