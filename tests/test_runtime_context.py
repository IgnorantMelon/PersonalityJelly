from personality_jelly.characters import create_character
from personality_jelly.domain import InteractionMode, Memory, MemoryScope, MemoryStatus
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import build_context_package, create_conversation, create_user
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
                    "claim_type": "personality",
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
                    "status": "verified",
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


def test_build_context_package_persists_prompt_with_persona_claims_and_memory(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text(
        "# 第一章\n\n林霜总是先观察，再行动。\n\n钟声响起时，她看向窗外。",
        encoding="utf-8",
    )
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
        user = create_user(session, display_name="测试用户", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        ).conversation
        MemoryRepository(session).add(
            Memory(
                id="mem_001",
                user_id=user.id,
                character_id="char_001",
                conversation_id=conversation.id,
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="用户喜欢夜里写作。",
                importance=0.7,
                reason="用户明确说明。",
            )
        )
        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="我今天写得很慢。",
        ).context_package
        session.commit()

    assert context.persona_version_id == persona.id
    assert context.claim_ids
    assert context.memory_ids == ["mem_001"]
    assert context.retrieved_chunk_ids
    assert "林霜谨慎敏锐" in context.assembled_prompt
    assert "林霜行事谨慎" in context.assembled_prompt
    assert "用户喜欢夜里写作" in context.assembled_prompt
    assert "# Retrieved Source Chunks" in context.assembled_prompt
    assert "林霜总是先观察，再行动。" in context.assembled_prompt
    assert "我今天写得很慢" in context.assembled_prompt


def test_build_context_package_infers_interaction_mode(tmp_path) -> None:
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
        user = create_user(session, display_name="测试用户", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        ).conversation

        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="假设我们现在进入你的原作场景，你会怎么行动？",
        ).context_package
        session.commit()

    assert context.interaction_mode == InteractionMode.ROLEPLAY_SCENE
    assert "# Interaction Mode\nroleplay_scene" in context.assembled_prompt

