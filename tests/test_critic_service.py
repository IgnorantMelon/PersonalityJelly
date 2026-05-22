import pytest
from pydantic import ValidationError

from personality_jelly.characters import create_character
from personality_jelly.critic import evaluate_message
from personality_jelly.domain import ClaimStatus, ClaimType
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import create_conversation, create_user, send_message
from personality_jelly.storage import (
    CharacterRepository,
    CriticReportRepository,
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
                    "claim_type": ClaimType.PERSONALITY,
                    "content": "林霜行事谨慎。",
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

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "core_self": "林霜谨慎敏锐。",
            "speech_rules": ["表达克制。"],
            "behavior_rules": ["先观察，再行动。"],
            "world_adaptation_rules": ["可以与现实用户交流。"],
            "forbidden_rules": ["不能改写原作经历。"],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class RoleplayFakeProvider:
    name = "roleplay-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        return "我听见了。先别急，我们把事情拆开看。"

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CriticFakeProvider:
    name = "critic-fake"

    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        return {
            "ooc_risk": "low",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["回复保持谨慎克制，未改写 canon。"],
            "suggested_action": "accept",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class InvalidCriticFakeProvider(CriticFakeProvider):
    name = "invalid-critic-fake"

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        return {
            "ooc_risk": "not_a_risk",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["invalid structured output"],
            "suggested_action": "accept",
        }


def test_evaluate_message_persists_critic_report(tmp_path) -> None:
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
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version
        user = create_user(session, user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        ).conversation
        turn = send_message(
            session,
            provider=RoleplayFakeProvider(),
            model_config=ModelConfig(model="fake-roleplay"),
            conversation_id=conversation.id,
            content="我今天有点累。",
        )
        critic = CriticFakeProvider()
        result = evaluate_message(
            session,
            provider=critic,
            model_config=ModelConfig(model="fake-critic"),
            message_id=turn.assistant_message.id,
        )
        session.commit()

    with session_factory() as session:
        stored = CriticReportRepository(session).require(result.critic_report.id)
        traces = LLMRawOutputRepository(session).list_by_operation("critic.evaluate_message")

    assert stored.message_id == turn.assistant_message.id
    assert stored.ooc_risk == "low"
    assert len(traces) == 1
    assert traces[0].schema_name == "CriticEvaluation"
    assert traces[0].model_name == "fake-critic"
    assert traces[0].parsed_output["suggested_action"] == "accept"
    assert traces[0].validation_errors == []

    with session_factory() as session:
        with pytest.raises(ValidationError):
            evaluate_message(
                session,
                provider=InvalidCriticFakeProvider(),
                model_config=ModelConfig(model="invalid-critic"),
                message_id=turn.assistant_message.id,
            )
        session.commit()

    with session_factory() as session:
        error_traces = LLMRawOutputRepository(session).list_by_operation(
            "critic.evaluate_message"
        )

    assert len(error_traces) == 2
    assert error_traces[0].model_name == "invalid-critic"
    assert error_traces[0].parsed_output is None
    assert error_traces[0].validation_errors
    assert '"ooc_risk": "not_a_risk"' in error_traces[0].raw_output
    assert stored.suggested_action == "accept"
    assert "我今天有点累" in critic.prompt
    assert "我听见了" in critic.prompt

