from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimConflict,
    ClaimStatus,
    EvidenceRef,
    MessageRole,
    SourceChunk,
)
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.storage import (
    CanonClaimRepository,
    ClaimConflictRepository,
    EvidenceRefRepository,
    SourceChunkRepository,
)
from personality_jelly.extraction.verifier_prompts import (
    VERIFIER_SYSTEM_PROMPT,
    build_verifier_user_prompt,
)
from personality_jelly.extraction.verifier_schemas import (
    VerifierConflict,
    VerifierDecision,
    VerifierResult,
)


@dataclass(frozen=True)
class CanonVerificationResult:
    updated_claims: list[CanonClaim]
    conflicts: list[ClaimConflict]


def verify_candidate_claims(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    character: Character,
) -> CanonVerificationResult:
    claim_repository = CanonClaimRepository(session)
    candidate_claims = claim_repository.list_by_character(
        character.id,
        status=ClaimStatus.CANDIDATE,
    )
    if not candidate_claims:
        return CanonVerificationResult(updated_claims=[], conflicts=[])

    evidence_by_claim = _load_evidence(session, candidate_claims)
    chunks_by_id = _load_chunks(session, evidence_by_claim)
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=VERIFIER_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_verifier_user_prompt(
                    character=character,
                    claims=candidate_claims,
                    evidence_by_claim=evidence_by_claim,
                    chunks_by_id=chunks_by_id,
                ),
            ),
        ],
        schema=VerifierResult.model_json_schema(),
        model_config=model_config,
    )
    verifier_result = TypeAdapter(VerifierResult).validate_python(raw)

    claim_ids = {claim.id for claim in candidate_claims}
    updated_claims = [
        _apply_decision(claim_repository, decision, claim_ids)
        for decision in verifier_result.decisions
    ]
    conflicts = [
        _persist_conflict(session, conflict, claim_ids)
        for conflict in verifier_result.conflicts
    ]
    return CanonVerificationResult(updated_claims=updated_claims, conflicts=conflicts)


def _load_evidence(
    session: Session,
    claims: list[CanonClaim],
) -> dict[str, list[EvidenceRef]]:
    evidence_repository = EvidenceRefRepository(session)
    return {
        claim.id: evidence_repository.list_by_claim(claim.id)
        for claim in claims
    }


def _load_chunks(
    session: Session,
    evidence_by_claim: dict[str, list[EvidenceRef]],
) -> dict[str, SourceChunk]:
    chunk_repository = SourceChunkRepository(session)
    chunk_ids = {
        evidence.chunk_id
        for evidence_refs in evidence_by_claim.values()
        for evidence in evidence_refs
    }
    return {chunk_id: chunk_repository.require(chunk_id) for chunk_id in chunk_ids}


def _apply_decision(
    repository: CanonClaimRepository,
    decision: VerifierDecision,
    claim_ids: set[str],
) -> CanonClaim:
    if decision.claim_id not in claim_ids:
        raise ValueError(f"Verifier returned unknown claim_id {decision.claim_id!r}")
    return repository.update_status(
        decision.claim_id,
        status=decision.status,
        reasoning=decision.reasoning,
        confidence=decision.confidence,
    )


def _persist_conflict(
    session: Session,
    conflict: VerifierConflict,
    claim_ids: set[str],
) -> ClaimConflict:
    if conflict.claim_a_id not in claim_ids:
        raise ValueError(f"Verifier returned unknown claim_a_id {conflict.claim_a_id!r}")
    if conflict.claim_b_id not in claim_ids:
        raise ValueError(f"Verifier returned unknown claim_b_id {conflict.claim_b_id!r}")
    claim_conflict = ClaimConflict(
        id=generate_id(EntityKind.CLAIM_CONFLICT),
        claim_a_id=conflict.claim_a_id,
        claim_b_id=conflict.claim_b_id,
        description=conflict.description,
        resolution=conflict.resolution,
    )
    return ClaimConflictRepository(session).add(claim_conflict)

