import pytest

from personality_jelly.domain import Character, ClaimStatus, ClaimType, SourceChunk
from personality_jelly.extraction import extract_candidate_claims
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig


class FakeProvider:
    name = "fake"

    def __init__(self, payload):
        self.payload = payload
        self.messages: list[ChatMessage] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.messages = messages
        return self.payload

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_extract_candidate_claims_converts_reader_schema_to_domain() -> None:
    chunk = SourceChunk(
        id="chunk_001",
        source_work_id="sw_001",
        paragraph_index=0,
        text="林霜总是先观察，再行动。",
    )
    character = Character(id="char_001", source_work_id="sw_001", canonical_name="林霜")
    provider = FakeProvider(
        {
            "claims": [
                {
                    "claim_type": "personality",
                    "content": "林霜行事谨慎，习惯先观察再行动。",
                    "confidence": 0.86,
                    "reasoning": "原文直接描述她的行动方式。",
                    "evidence": [
                        {
                            "chunk_id": "chunk_001",
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.9,
                        }
                    ],
                }
            ]
        }
    )

    result = extract_candidate_claims(
        provider=provider,
        model_config=ModelConfig(model="fake-model"),
        source_work_id="sw_001",
        character=character,
        chunks=[chunk],
    )

    assert result.claims[0].status == ClaimStatus.CANDIDATE
    assert result.claims[0].claim_type == ClaimType.PERSONALITY
    assert result.claims[0].created_by == "reader"
    assert result.evidence_refs[0].claim_id == result.claims[0].id
    assert result.evidence_refs[0].chunk_id == "chunk_001"
    assert "林霜" in provider.messages[1].content


def test_extract_candidate_claims_rejects_unknown_evidence_chunk() -> None:
    chunk = SourceChunk(
        id="chunk_001",
        source_work_id="sw_001",
        paragraph_index=0,
        text="林霜总是先观察，再行动。",
    )
    character = Character(id="char_001", source_work_id="sw_001", canonical_name="林霜")
    provider = FakeProvider(
        {
            "claims": [
                {
                    "claim_type": "personality",
                    "content": "林霜行事谨慎。",
                    "confidence": 0.7,
                    "evidence": [
                        {
                            "chunk_id": "missing",
                            "excerpt": "不存在",
                            "support_score": 0.2,
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="unknown chunk_id"):
        extract_candidate_claims(
            provider=provider,
            model_config=ModelConfig(model="fake-model"),
            source_work_id="sw_001",
            character=character,
            chunks=[chunk],
        )

