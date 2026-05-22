from personality_jelly.characters import create_character
from personality_jelly.domain import (
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceWork,
)
from personality_jelly.domain.models import utc_now
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import build_context_package, create_conversation, create_user
from personality_jelly.storage import (
    CharacterRepository,
    ConversationRepository,
    LLMRawOutputRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
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


class ModeClassifierFakeProvider:
    name = "mode-classifier-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "mode": "roleplay_scene",
            "confidence": 0.92,
            "reasoning": "fake provider classified the requested mode.",
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
            mode_provider=ModeClassifierFakeProvider(),
            mode_model_config=ModelConfig(model="fake-mode"),
        ).context_package
        session.commit()

    with session_factory() as session:
        traces = LLMRawOutputRepository(session).list_by_operation(
            "runtime.mode.classify_interaction_mode"
        )

    assert context.interaction_mode == InteractionMode.ROLEPLAY_SCENE
    assert "# Interaction Mode\nroleplay_scene" in context.assembled_prompt
    assert len(traces) == 1
    assert traces[0].schema_name == "InteractionModeClassification"
    assert traces[0].model_name == "fake-mode"
    assert traces[0].parsed_output["mode"] == "roleplay_scene"


def test_build_context_package_renders_layered_conversation_summary_as_context_only() -> None:
    summary = "\n".join(
        [
            "# Short-term Scene State",
            "The user is planning a quiet drafting scene.",
            "",
            "# User Memory Candidates",
            "- User prefers late-night writing.",
            "",
            "# Relationship Memory Notes",
            "- User trusts Lin Shuang with early drafts.",
            "",
            "# Reflective Notes",
            "- Keep co-created fiction separate from canon.",
        ]
    )

    prompt, memory_ids, memories = _build_context_for_summary(summary)

    assert "# Conversation Summary" in prompt
    assert "## short_term_scene_state\nThe user is planning a quiet drafting scene." in prompt
    assert "## user_memory_candidates\n- User prefers late-night writing." in prompt
    assert "## relationship_memory_notes\n- User trusts Lin Shuang with early drafts." in prompt
    assert "## reflective_notes\n- Keep co-created fiction separate from canon." in prompt
    assert memory_ids == []
    assert memories == []


def test_build_context_package_renders_legacy_summary_as_short_term_scene_state() -> None:
    prompt, _, _ = _build_context_for_summary("Legacy unlayered summary.")

    assert "## short_term_scene_state\nLegacy unlayered summary." in prompt
    assert "## user_memory_candidates\n- none" in prompt
    assert "## relationship_memory_notes\n- none" in prompt
    assert "## reflective_notes\n- none" in prompt


def test_build_context_package_renders_empty_summary_layers_with_none_state() -> None:
    prompt, _, _ = _build_context_for_summary(None)

    assert "## short_term_scene_state\nnone" in prompt
    assert "## user_memory_candidates\n- none" in prompt
    assert "## relationship_memory_notes\n- none" in prompt
    assert "## reflective_notes\n- none" in prompt


def _build_context_for_summary(summary: str | None) -> tuple[str, list[str], list[Memory]]:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Sample Work", source_type="markdown")
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                source_work_id="sw_001",
                character_id="char_001",
                version_number=1,
                core_self="Lin Shuang is observant and careful.",
            )
        )
        user = create_user(session, display_name="Test User", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id="pv_001",
            conversation_id="conv_001",
        ).conversation
        if summary is not None:
            ConversationRepository(session).update_summary(
                conversation.id,
                summary=summary,
                updated_at=utc_now(),
            )

        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="I want to continue the scene.",
        ).context_package
        memories = MemoryRepository(session).list_for_user_character(user.id, "char_001")
        session.commit()

    return context.assembled_prompt, context.memory_ids, memories

