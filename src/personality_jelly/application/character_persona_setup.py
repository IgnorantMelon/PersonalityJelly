from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.application.providers import (
    PersonaSetupModelRoleBundle,
    PersonaSetupProviderRoleBundle,
    build_persona_setup_role_bundles,
)
from personality_jelly.domain import Character, ClaimStatus, PersonaVersion, SourceWork
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.llm.tracing import LLMTraceRecorder
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


@dataclass(frozen=True)
class PersonaSetupTraceRecorders:
    reader: LLMTraceRecorder | None = None
    verifier: LLMTraceRecorder | None = None
    persona_compiler: LLMTraceRecorder | None = None


def build_character_persona(
    session: Session,
    *,
    source_work_id: str,
    character_id: str,
    provider: LLMProvider | None = None,
    model_config: ModelConfig | None = None,
    provider_roles: PersonaSetupProviderRoleBundle | None = None,
    model_roles: PersonaSetupModelRoleBundle | None = None,
    trace_recorders: PersonaSetupTraceRecorders | None = None,
    max_chunks: int | None = None,
) -> CharacterPersonaSetupResult:
    provider_roles, model_roles = _resolve_setup_role_bundles(
        provider=provider,
        model_config=model_config,
        provider_roles=provider_roles,
        model_roles=model_roles,
    )
    source_work = SourceWorkRepository(session).require(source_work_id)
    character = CharacterRepository(session).require(character_id)
    if character.source_work_id != source_work.id:
        raise ValueError(
            f"Character {character.id!r} does not belong to source work {source_work.id!r}"
        )

    extraction = run_reader_extraction(
        session,
        provider=provider_roles.reader,
        model_config=model_roles.reader,
        character_id=character.id,
        max_chunks=max_chunks,
        trace_recorder=trace_recorders.reader if trace_recorders else None,
    )
    verification = verify_candidate_claims(
        session,
        provider=provider_roles.verifier,
        model_config=model_roles.verifier,
        character=CharacterRepository(session).require(character.id),
        trace_recorder=trace_recorders.verifier if trace_recorders else None,
    )
    compilation = compile_persona_version(
        session,
        provider=provider_roles.persona_compiler,
        model_config=model_roles.persona_compiler,
        character_id=character.id,
        trace_recorder=trace_recorders.persona_compiler if trace_recorders else None,
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


def _resolve_setup_role_bundles(
    *,
    provider: LLMProvider | None,
    model_config: ModelConfig | None,
    provider_roles: PersonaSetupProviderRoleBundle | None,
    model_roles: PersonaSetupModelRoleBundle | None,
) -> tuple[PersonaSetupProviderRoleBundle, PersonaSetupModelRoleBundle]:
    if provider_roles is not None or model_roles is not None:
        if provider_roles is None or model_roles is None:
            raise ValueError("provider_roles and model_roles must be supplied together")
        if provider is not None or model_config is not None:
            raise ValueError("provider/model_config cannot be combined with setup role bundles")
        return provider_roles, model_roles

    if provider is None or model_config is None:
        raise ValueError("provider and model_config are required")
    return build_persona_setup_role_bundles(provider=provider, model_config=model_config)
