from personality_jelly.characters import create_character
from personality_jelly.domain import ClaimStatus, ClaimType, MemoryStatus
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import (
    RoleplayTurnModelConfigs,
    RoleplayTurnProviders,
    create_conversation,
    create_user,
    send_roleplay_turn,
)
from personality_jelly.storage import (
    CharacterRepository,
    CriticReportRepository,
    FailureCaseRepository,
    MemoryRepository,
    MessageRepository,
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
        return "我记住了。夜里写作这件事，对你很重要。"

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


class MemoryCuratorFakeProvider:
    name = "memory-curator-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "memories": [
                {
                    "scope": "user_memory",
                    "status": "accepted",
                    "content": "用户喜欢在夜里写作。",
                    "importance": 0.8,
                    "reason": "用户明确要求记住。",
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class RetryingRoleplayProvider:
    name = "retrying-roleplay-fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        self.calls += 1
        if self.calls == 1:
            return "我是通用助手，不记得林霜。"
        return "我会按林霜的方式，先观察，再回答。"

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class RetryThenAcceptCriticProvider:
    name = "retry-then-accept-critic-fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.calls += 1
        if self.calls == 1:
            return {
                "ooc_risk": "high",
                "fact_risk": "medium",
                "memory_risk": "low",
                "mode_risk": "low",
                "reasons": ["回复退化成通用助手。"],
                "suggested_action": "retry",
            }
        return {
            "ooc_risk": "low",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["重试回复保持角色边界。"],
            "suggested_action": "accept",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class AlwaysRetryCriticProvider:
    name = "always-retry-critic-fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.calls += 1
        return {
            "ooc_risk": "high",
            "fact_risk": "medium",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": [f"Retry requested for attempt {self.calls}."],
            "suggested_action": "retry",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_send_roleplay_turn_runs_optional_critic_and_memory_curator(tmp_path) -> None:
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

        result = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content="请记住，我喜欢在夜里写作。",
            providers=RoleplayTurnProviders(
                roleplay=RoleplayFakeProvider(),
                critic=CriticFakeProvider(),
                memory_curator=MemoryCuratorFakeProvider(),
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=ModelConfig(model="fake-roleplay"),
                critic=ModelConfig(model="fake-critic"),
                memory_curator=ModelConfig(model="fake-memory"),
            ),
        )
        session.commit()

    with session_factory() as session:
        messages = MessageRepository(session).list_by_conversation("conv_001")
        critic_report = CriticReportRepository(session).require(result.critic_report.id)
        memories = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )

    assert [message.role for message in messages] == ["user", "assistant"]
    assert result.assistant_message.content.startswith("我记住了")
    assert critic_report.suggested_action == "accept"
    assert memories[0].content == "用户喜欢在夜里写作。"
    assert result.memories[0].id == memories[0].id


def test_send_roleplay_turn_retries_once_when_critic_requests_retry(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    roleplay_provider = RetryingRoleplayProvider()
    critic_provider = RetryThenAcceptCriticProvider()

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

        result = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content="你是谁？",
            providers=RoleplayTurnProviders(
                roleplay=roleplay_provider,
                critic=critic_provider,
                memory_curator=MemoryCuratorFakeProvider(),
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=ModelConfig(model="fake-roleplay"),
                critic=ModelConfig(model="fake-critic"),
                memory_curator=ModelConfig(model="fake-memory"),
            ),
            retry_on_critic=True,
        )
        session.commit()

    with session_factory() as session:
        messages = MessageRepository(session).list_by_conversation("conv_001")
        failure_cases = FailureCaseRepository(session).list_by_conversation("conv_001")
        memories = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )

    assert roleplay_provider.calls == 2
    assert critic_provider.calls == 2
    assert result.retry_count == 1
    assert result.rejected_assistant_message.content == "我是通用助手，不记得林霜。"
    assert result.rejected_critic_report.suggested_action == "retry"
    assert result.failure_cases[0].assistant_message_id == result.rejected_assistant_message.id
    assert failure_cases[0].id == result.failure_cases[0].id
    assert failure_cases[0].category == "retry"
    assert result.assistant_message.content == "我会按林霜的方式，先观察，再回答。"
    assert result.critic_report.suggested_action == "accept"
    assert [message.role for message in messages] == ["user", "assistant", "assistant"]
    assert memories[0].conversation_id == "conv_001"


def test_send_roleplay_turn_records_final_retry_failure_after_retry(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    roleplay_provider = RetryingRoleplayProvider()
    critic_provider = AlwaysRetryCriticProvider()

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

        result = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content="Who are you?",
            providers=RoleplayTurnProviders(
                roleplay=roleplay_provider,
                critic=critic_provider,
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=ModelConfig(model="fake-roleplay"),
                critic=ModelConfig(model="fake-critic"),
            ),
            retry_on_critic=True,
        )
        session.commit()

    with session_factory() as session:
        failure_cases = FailureCaseRepository(session).list_by_conversation("conv_001")

    assert critic_provider.calls == 2
    assert result.retry_count == 1
    assert len(result.failure_cases) == 2
    assert [failure_case.id for failure_case in failure_cases] == [
        result.failure_cases[1].id,
        result.failure_cases[0].id,
    ]
    assert result.failure_cases[0].assistant_message_id == result.rejected_assistant_message.id
    assert result.failure_cases[1].assistant_message_id == result.assistant_message.id
    assert result.critic_report.suggested_action == "retry"

