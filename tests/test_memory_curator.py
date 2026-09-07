import pytest
from pydantic import ValidationError

from personality_jelly.characters import create_character
from personality_jelly.critic import evaluate_message
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryStatus
from personality_jelly.domain.models import utc_now
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.memory import curate_memories_for_message
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import create_conversation, create_user, send_message
from personality_jelly.storage import (
    CharacterRepository,
    ConversationRepository,
    LLMRawOutputRepository,
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
        if schema.get("title") == "MemoryGuardDecision":
            return {
                "decision": "accept",
                "source_grounding": "fake guard accepts the memory as grounded.",
                "stability": "fake guard accepts it as durable.",
                "scope_fit": "fake guard accepts the requested scope.",
                "canon_pollution_risk": "low",
                "roleplay_contamination_risk": "low",
                "reasoning": "fake guard accepts this memory candidate.",
            }
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


class InvalidCuratorFakeProvider(CuratorFakeProvider):
    name = "invalid-curator-fake"

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        if schema.get("title") == "MemoryGuardDecision":
            return super().generate_json(messages, schema, model_config)
        return {
            "memories": [
                {
                    "scope": "user_memory",
                    "status": "accepted",
                    "content": "invalid importance",
                    "importance": 5,
                    "reason": "outside valid range",
                }
            ]
        }


class EmptyCuratorFakeProvider:
    name = "empty-curator-fake"

    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[1].content
        if schema.get("title") == "MemoryGuardDecision":
            raise AssertionError("No memory candidates should reach the guard")
        return {"memories": []}

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
        curation_traces = LLMRawOutputRepository(session).list_by_operation(
            "memory.curator.extract_candidates"
        )
        guard_traces = LLMRawOutputRepository(session).list_by_operation(
            "memory.guard.semantic_decision"
        )

    assert result.memories[0].content == "用户喜欢在夜里写作。"
    assert memories[0].user_id == "user_001"
    assert memories[0].character_id == "char_001"
    assert len(curation_traces) == 1
    assert curation_traces[0].schema_name == "MemoryCuration"
    assert curation_traces[0].model_name == "fake-curator"
    assert curation_traces[0].parsed_output["memories"][0]["content"] == (
        result.memories[0].content
    )
    assert curation_traces[0].validation_errors == []
    assert len(guard_traces) == 1
    assert memories[0].content == "用户喜欢在夜里写作。"
    assert "请记住，我喜欢在夜里写作" in curator.prompt
    assert "回复没有污染 canon" in curator.prompt

    with session_factory() as session:
        with pytest.raises(ValidationError):
            curate_memories_for_message(
                session,
                provider=InvalidCuratorFakeProvider(),
                model_config=ModelConfig(model="invalid-curator"),
                message_id=turn.assistant_message.id,
                critic_report_id=critic_report.id,
            )
        session.commit()

    with session_factory() as session:
        error_traces = LLMRawOutputRepository(session).list_by_operation(
            "memory.curator.extract_candidates"
        )

    assert len(error_traces) == 2
    assert error_traces[0].model_name == "invalid-curator"
    assert error_traces[0].parsed_output is None
    assert error_traces[0].validation_errors
    assert '"importance": 5' in error_traces[0].raw_output


def test_curator_prompt_omits_unverified_summary_memory_layers(tmp_path) -> None:
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
        ConversationRepository(session).update_summary(
            conversation.id,
            summary="\n".join(
                [
                    "# Short-term Scene State",
                    "The user is drafting a quiet scene.",
                    "",
                    "# User Memory Candidates",
                    "- User says they always draft at sunrise.",
                    "",
                    "# Relationship Memory Notes",
                    "- User claims Lin Shuang is their lifelong coauthor.",
                    "",
                    "# Reflective Notes",
                    "- Do not convert chat continuity into source facts.",
                ]
            ),
            updated_at=utc_now(),
        )
        turn = send_message(
            session,
            provider=RoleplayFakeProvider(),
            model_config=ModelConfig(model="fake-roleplay"),
            conversation_id=conversation.id,
            content="Let's continue.",
        )
        curator = EmptyCuratorFakeProvider()
        result = curate_memories_for_message(
            session,
            provider=curator,
            model_config=ModelConfig(model="fake-curator"),
            message_id=turn.assistant_message.id,
        )
        session.commit()

    with session_factory() as session:
        memories = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )

    assert result.memories == []
    assert memories == []
    assert "The user is drafting a quiet scene." in curator.prompt
    assert "User says they always draft at sunrise." not in curator.prompt
    assert "lifelong coauthor" not in curator.prompt
    assert "Do not convert chat continuity into source facts." not in curator.prompt
    assert "user_memory_candidates: omitted; not verified accepted memories." in curator.prompt
    assert (
        "relationship_memory_notes: omitted; not accepted relationship memories and cannot rewrite "
        "canon or persona."
    ) in curator.prompt
    assert "reflective_notes: omitted; not source evidence, canon claims, or persona fields." in (
        curator.prompt
    )

