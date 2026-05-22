import pytest
from pydantic import ValidationError

from personality_jelly.characters import create_character
from personality_jelly.domain import ClaimStatus, ClaimType
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ClaimConflictRepository,
    LLMRawOutputRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class ReaderFakeProvider:
    name = "reader-fake"

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "claims": [
                {
                    "claim_type": "personality",
                    "content": "林霜行事谨慎。",
                    "confidence": 0.8,
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.9,
                        }
                    ],
                },
                {
                    "claim_type": "personality",
                    "content": "林霜行事鲁莽。",
                    "confidence": 0.4,
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.2,
                        }
                    ],
                },
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class VerifierFakeProvider:
    name = "verifier-fake"

    def __init__(self) -> None:
        self.claim_ids: list[str] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        content = messages[1].content
        self.claim_ids = [
            line.split(": ", 1)[1]
            for line in content.splitlines()
            if line.startswith("claim_id: ")
        ]
        cautious_claim_id, reckless_claim_id = self.claim_ids
        return {
            "decisions": [
                {
                    "claim_id": cautious_claim_id,
                    "status": "verified",
                    "confidence": 0.92,
                    "reasoning": "证据支持她先观察再行动。",
                },
                {
                    "claim_id": reckless_claim_id,
                    "status": "conflicted",
                    "confidence": 0.3,
                    "reasoning": "该说法与谨慎行动的证据冲突。",
                },
            ],
            "conflicts": [
                {
                    "claim_a_id": cautious_claim_id,
                    "claim_b_id": reckless_claim_id,
                    "description": "谨慎与鲁莽描述互相冲突。",
                    "resolution": "保留谨慎说法。",
                }
            ],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class InvalidVerifierFakeProvider(VerifierFakeProvider):
    name = "invalid-verifier-fake"

    def generate_json(self, messages, schema, model_config):
        return {
            "decisions": [
                {
                    "claim_id": "claim_invalid",
                    "status": "verified",
                    "confidence": 2,
                    "reasoning": "outside valid range",
                }
            ],
            "conflicts": [],
        }


def test_verify_candidate_claims_updates_claim_status_and_records_conflict(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="样本文本")
        chunk_id = ingestion_result.chunks[0].id
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="林霜",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(chunk_id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        session.commit()

    with session_factory() as session:
        character = CharacterRepository(session).require("char_001")
        result = verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        session.commit()

    with session_factory() as session:
        verified_claims = CanonClaimRepository(session).list_by_character(
            "char_001",
            status=ClaimStatus.VERIFIED,
            claim_type=ClaimType.PERSONALITY,
        )
        conflicted_claims = CanonClaimRepository(session).list_by_character(
            "char_001",
            status=ClaimStatus.CONFLICTED,
            claim_type=ClaimType.PERSONALITY,
        )
        conflicts = ClaimConflictRepository(session).list_by_claim(conflicted_claims[0].id)
        traces = LLMRawOutputRepository(session).list_by_operation(
            "extraction.verifier.verify_claim"
        )

    assert len(result.updated_claims) == 2
    assert len(traces) == 1
    assert traces[0].schema_name == "VerifierResult"
    assert traces[0].model_name == "fake-verifier"
    assert traces[0].parsed_output["decisions"][0]["status"] == "verified"
    assert traces[0].validation_errors == []
    assert verified_claims[0].content == "林霜行事谨慎。"
    assert verified_claims[0].reasoning == "证据支持她先观察再行动。"
    assert conflicted_claims[0].content == "林霜行事鲁莽。"
    assert conflicts[0].description == "谨慎与鲁莽描述互相冲突。"


def test_verify_candidate_claims_traces_validation_errors(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="sample")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        with pytest.raises(ValidationError):
            verify_candidate_claims(
                session,
                provider=InvalidVerifierFakeProvider(),
                model_config=ModelConfig(model="invalid-verifier"),
                character=character,
            )
        session.commit()

    with session_factory() as session:
        traces = LLMRawOutputRepository(session).list_by_operation(
            "extraction.verifier.verify_claim"
        )

    assert len(traces) == 1
    assert traces[0].schema_name == "VerifierResult"
    assert traces[0].model_name == "invalid-verifier"
    assert traces[0].parsed_output is None
    assert traces[0].validation_errors
    assert '"confidence": 2' in traces[0].raw_output

