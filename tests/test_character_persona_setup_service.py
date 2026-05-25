from pathlib import Path

import pytest

from personality_jelly.application import build_character_persona
from personality_jelly.characters import create_character
from personality_jelly.domain import SourceWork
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    PersonaVersionRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class SetupFakeProvider:
    name = "setup-fake"

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        properties = schema.get("properties", {})
        if "claims" in properties:
            return {
                "claims": [
                    {
                        "claim_type": "personality",
                        "content": "Lin Shuang acts carefully.",
                        "confidence": 0.9,
                        "evidence": [
                            {
                                "chunk_id": self.chunk_id,
                                "excerpt": "Lin Shuang observes before acting.",
                                "support_score": 0.95,
                            }
                        ],
                    },
                    {
                        "claim_type": "event",
                        "content": "Lin Shuang rushes into danger.",
                        "confidence": 0.4,
                        "evidence": [
                            {
                                "chunk_id": self.chunk_id,
                                "excerpt": "Lin Shuang observes before acting.",
                                "support_score": 0.2,
                            }
                        ],
                    },
                ]
            }
        if "decisions" in properties:
            claim_ids = [
                line.split(": ", 1)[1]
                for line in messages[1].content.splitlines()
                if line.startswith("claim_id: ")
            ]
            careful_claim_id, reckless_claim_id = claim_ids
            return {
                "decisions": [
                    {
                        "claim_id": careful_claim_id,
                        "status": "verified",
                        "confidence": 0.93,
                        "reasoning": "The evidence directly supports careful action.",
                    },
                    {
                        "claim_id": reckless_claim_id,
                        "status": "conflicted",
                        "confidence": 0.25,
                        "reasoning": "The evidence conflicts with reckless action.",
                    },
                ],
                "conflicts": [
                    {
                        "claim_a_id": careful_claim_id,
                        "claim_b_id": reckless_claim_id,
                        "description": "Careful and reckless behavior conflict.",
                        "resolution": "Keep the careful behavior claim.",
                    }
                ],
            }
        if "core_self" in properties:
            return {
                "core_self": "Lin Shuang is cautious and observant.",
                "speech_rules": ["Speak with restraint."],
                "behavior_rules": ["Observe before acting."],
                "world_adaptation_rules": ["Use canon experiences to interpret the world."],
                "forbidden_rules": ["Do not rewrite canon events."],
            }
        raise AssertionError(f"Unexpected schema properties: {sorted(properties)}")

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        raise NotImplementedError


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def test_build_character_persona_returns_setup_ids(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# Chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    session_factory = _session_factory()

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="sample")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        result = build_character_persona(
            session,
            source_work_id=ingestion_result.source_work.id,
            character_id="char_001",
            provider=SetupFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="setup-fake"),
        )
        session.commit()

    assert result.source_work.id == result.source_work_id
    assert result.character.id == result.character_id
    assert result.character_id == "char_001"
    assert len(result.candidate_claim_ids) == 2
    assert len(result.evidence_ref_ids) == 2
    assert len(result.verified_claim_ids) == 1
    assert len(result.conflict_ids) == 1
    assert result.persona_version.id == result.persona_version_id
    assert result.persona_version.source_claim_ids == result.verified_claim_ids

    with session_factory() as session:
        stored_persona = PersonaVersionRepository(session).require(result.persona_version_id)

    assert stored_persona.source_claim_ids == result.verified_claim_ids


def test_build_character_persona_requires_matching_source_work() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="source one", source_type="markdown")
        )
        SourceWorkRepository(session).add(
            SourceWork(id="sw_002", title="source two", source_type="markdown")
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            character_id="char_001",
        )

        with pytest.raises(ValueError, match="does not belong to source work"):
            build_character_persona(
                session,
                source_work_id="sw_002",
                character_id="char_001",
                provider=SetupFakeProvider("chunk_001"),
                model_config=ModelConfig(model="setup-fake"),
            )
