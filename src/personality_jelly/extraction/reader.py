from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    EvidenceRef,
    MessageRole,
    SourceChunk,
)
from personality_jelly.extraction.prompts import READER_SYSTEM_PROMPT, build_reader_user_prompt
from personality_jelly.extraction.schemas import ReaderClaim, ReaderExtraction
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import LLMTraceRecorder, record_structured_output


READER_EXTRACTION_OPERATION = "extraction.reader.extract_candidate_claims"


@dataclass(frozen=True)
class ReaderExtractionResult:
    claims: list[CanonClaim]
    evidence_refs: list[EvidenceRef]


def extract_candidate_claims(
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    source_work_id: str,
    character: Character,
    chunks: list[SourceChunk],
    trace_recorder: LLMTraceRecorder | None = None,
) -> ReaderExtractionResult:
    if not chunks:
        return ReaderExtractionResult(claims=[], evidence_refs=[])

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=READER_SYSTEM_PROMPT),
        ChatMessage(
            role=MessageRole.USER,
            content=build_reader_user_prompt(
                canonical_name=character.canonical_name,
                aliases=character.aliases,
                chunks=[(chunk.id, chunk.text) for chunk in chunks],
            ),
        ),
    ]
    schema = ReaderExtraction.model_json_schema()
    raw = provider.generate_json(
        messages=messages,
        schema=schema,
        model_config=model_config,
    )
    try:
        extraction = TypeAdapter(ReaderExtraction).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=READER_EXTRACTION_OPERATION,
            schema_name=ReaderExtraction.__name__,
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=READER_EXTRACTION_OPERATION,
        schema_name=ReaderExtraction.__name__,
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=extraction,
    )

    chunk_ids = {chunk.id for chunk in chunks}
    claims: list[CanonClaim] = []
    evidence_refs: list[EvidenceRef] = []
    for claim in extraction.claims:
        claim_id = generate_id(EntityKind.CANON_CLAIM)
        claims.append(_claim_to_domain(claim, claim_id, source_work_id, character.id))
        for evidence in claim.evidence:
            if evidence.chunk_id not in chunk_ids:
                raise ValueError(f"Evidence references unknown chunk_id {evidence.chunk_id!r}")
            evidence_refs.append(
                EvidenceRef(
                    id=generate_id(EntityKind.EVIDENCE_REF),
                    claim_id=claim_id,
                    chunk_id=evidence.chunk_id,
                    excerpt=evidence.excerpt,
                    support_score=evidence.support_score,
                )
            )

    return ReaderExtractionResult(claims=claims, evidence_refs=evidence_refs)


def _claim_to_domain(
    claim: ReaderClaim,
    claim_id: str,
    source_work_id: str,
    character_id: str,
) -> CanonClaim:
    return CanonClaim(
        id=claim_id,
        source_work_id=source_work_id,
        character_id=character_id,
        claim_type=claim.claim_type,
        content=claim.content,
        status=ClaimStatus.CANDIDATE,
        confidence=claim.confidence,
        reasoning=claim.reasoning,
        created_by="reader",
    )

