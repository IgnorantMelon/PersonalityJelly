import pytest
from pydantic import ValidationError

from personality_jelly.characters import create_character
from personality_jelly.domain import ClaimStatus, ClaimType
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import (
    CharacterRepository,
    LLMRawOutputRepository,
    PersonaVersionRepository,
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
                    "claim_type": ClaimType.PERSONALITY,
                    "content": "林霜行事谨慎，习惯先观察再行动。",
                    "confidence": 0.9,
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.95,
                        }
                    ],
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class VerifierFakeProvider:
    name = "verifier-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        claim_id = next(
            line.split(": ", 1)[1]
            for line in messages[1].content.splitlines()
            if line.startswith("claim_id: ")
        )
        return {
            "decisions": [
                {
                    "claim_id": claim_id,
                    "status": ClaimStatus.VERIFIED,
                    "confidence": 0.95,
                    "reasoning": "证据直接支持。",
                }
            ],
            "conflicts": [],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CompilerFakeProvider:
    name = "compiler-fake"

    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        return {
            "core_self": "林霜谨慎敏锐，行动前会先观察局势。",
            "speech_rules": ["表达克制，少用夸张语气。"],
            "behavior_rules": ["先判断风险，再采取行动。"],
            "world_adaptation_rules": ["可以与现实用户交流，但以自身经验理解现实概念。"],
            "forbidden_rules": ["不能把用户闲聊改写为原作经历。"],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class InvalidCompilerFakeProvider(CompilerFakeProvider):
    name = "invalid-compiler-fake"

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        return {
            "speech_rules": ["missing core_self"],
            "behavior_rules": [],
            "world_adaptation_rules": [],
            "forbidden_rules": [],
        }


def test_compile_persona_version_uses_verified_claims_only(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="样本文本")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="林霜",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        session.commit()

    with session_factory() as session:
        character_model = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character_model,
        )
        compiler = CompilerFakeProvider()
        result = compile_persona_version(
            session,
            provider=compiler,
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        )
        session.commit()

    with session_factory() as session:
        stored = PersonaVersionRepository(session).latest_for_character("char_001")
        traces = LLMRawOutputRepository(session).list_by_operation("persona.compile_version")

    assert result.persona_version.version_number == 1
    assert len(traces) == 1
    assert traces[0].schema_name == "PersonaCompilation"
    assert traces[0].model_name == "fake-compiler"
    assert traces[0].parsed_output["core_self"] == result.persona_version.core_self
    assert traces[0].validation_errors == []
    assert stored.core_self == "林霜谨慎敏锐，行动前会先观察局势。"
    assert stored.source_claim_ids == result.persona_version.source_claim_ids
    assert "林霜行事谨慎" in compiler.prompt


def test_compile_persona_version_traces_validation_errors(tmp_path) -> None:
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
        character_model = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character_model,
        )
        with pytest.raises(ValidationError):
            compile_persona_version(
                session,
                provider=InvalidCompilerFakeProvider(),
                model_config=ModelConfig(model="invalid-compiler"),
                character_id="char_001",
            )
        session.commit()

    with session_factory() as session:
        traces = LLMRawOutputRepository(session).list_by_operation("persona.compile_version")

    assert len(traces) == 1
    assert traces[0].schema_name == "PersonaCompilation"
    assert traces[0].model_name == "invalid-compiler"
    assert traces[0].parsed_output is None
    assert traces[0].validation_errors
    assert '"speech_rules": ["missing core_self"]' in traces[0].raw_output
