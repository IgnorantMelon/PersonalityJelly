from personality_jelly.characters import create_character
from personality_jelly.critic import evaluate_message
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryStatus
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.memory import curate_memories_for_message
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import create_conversation, create_user, send_message
from personality_jelly.storage import (
    CharacterRepository,
    MemoryRepository,
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
        return "我记住了，你喜欢在夜里写作。"

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CriticFakeProvider:
    name = "critic-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "ooc_risk": "low",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["回复没有污染 canon。"],
            "suggested_action": "accept",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CuratorFakeProvider:
    name = "curator-fake"

    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        return {
            "memories": [
                {
                    "scope": "user_memory",
                    "status": "accepted",
                    "content": "用户喜欢在夜里写作。",
                    "importance": 0.8,
                    "reason": "用户明确告诉角色这一偏好。",
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_curate_memories_for_message_persists_memory(tmp_path) -> None:
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
            content="请记住，我喜欢在夜里写作。",
        )
        critic_report = evaluate_message(
            session,
            provider=CriticFakeProvider(),
            model_config=ModelConfig(model="fake-critic"),
            message_id=turn.assistant_message.id,
        ).critic_report
        curator = CuratorFakeProvider()
        result = curate_memories_for_message(
            session,
            provider=curator,
            model_config=ModelConfig(model="fake-curator"),
            message_id=turn.assistant_message.id,
            critic_report_id=critic_report.id,
        )
        session.commit()

    with session_factory() as session:
        memories = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )

    assert result.memories[0].content == "用户喜欢在夜里写作。"
    assert memories[0].user_id == "user_001"
    assert memories[0].character_id == "char_001"
    assert memories[0].content == "用户喜欢在夜里写作。"
    assert "请记住，我喜欢在夜里写作" in curator.prompt
    assert "回复没有污染 canon" in curator.prompt

