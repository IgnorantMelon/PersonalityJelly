from pathlib import Path

from personality_jelly.characters import create_character
from personality_jelly.domain import ClaimStatus, ClaimType
from personality_jelly.extraction import run_reader_extraction
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    CanonClaimRepository,
    EvidenceRefRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class FakeProvider:
    name = "fake"

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "claims": [
                {
                    "claim_type": "personality",
                    "content": "林霜习惯先观察再行动。",
                    "confidence": 0.88,
                    "reasoning": "原文直接描述了她的行动方式。",
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.92,
                        }
                    ],
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_run_reader_extraction_persists_claims_and_evidence(tmp_path: Path) -> None:
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
        session.commit()

    with session_factory() as session:
        provider = FakeProvider(chunk_id)
        result = run_reader_extraction(
            session,
            provider=provider,
            model_config=ModelConfig(model="fake-model"),
            character_id="char_001",
        )
        session.commit()

    with session_factory() as session:
        claims = CanonClaimRepository(session).list_by_character(
            "char_001",
            status=ClaimStatus.CANDIDATE,
            claim_type=ClaimType.PERSONALITY,
        )
        evidence = EvidenceRefRepository(session).list_by_claim(claims[0].id)

    assert result.claims[0].content == "林霜习惯先观察再行动。"
    assert claims[0].created_by == "reader"
    assert evidence[0].excerpt == "林霜总是先观察，再行动。"
