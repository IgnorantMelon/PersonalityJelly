from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.domain import CanonClaim, EvidenceRef, SourceChunk
from personality_jelly.extraction.reader import extract_candidate_claims
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    EvidenceRefRepository,
    LLMRawOutputRepository,
    SourceChunkRepository,
)


@dataclass(frozen=True)
class ExtractionPersistenceResult:
    claims: list[CanonClaim]
    evidence_refs: list[EvidenceRef]
    chunks: list[SourceChunk]


def run_reader_extraction(
    session: Session,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    character_id: str,
    max_chunks: int | None = None,
) -> ExtractionPersistenceResult:
    character = CharacterRepository(session).require(character_id)
    chunks = SourceChunkRepository(session).list_by_source_work(character.source_work_id)
    selected_chunks = chunks if max_chunks is None else chunks[:max_chunks]

    result = extract_candidate_claims(
        provider=provider,
        model_config=model_config,
        source_work_id=character.source_work_id,
        character=character,
        chunks=selected_chunks,
        trace_recorder=RepositoryLLMTraceRecorder(LLMRawOutputRepository(session)),
    )

    claim_repository = CanonClaimRepository(session)
    evidence_repository = EvidenceRefRepository(session)
    for claim in result.claims:
        claim_repository.add(claim)
    evidence_repository.add_many(result.evidence_refs)

    return ExtractionPersistenceResult(
        claims=result.claims,
        evidence_refs=result.evidence_refs,
        chunks=selected_chunks,
    )
