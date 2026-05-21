from personality_jelly.characters import create_character
from personality_jelly.domain import Message, MessageRole, PersonaVersion, SourceWork, User
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.runtime import (
    create_conversation,
    parse_layered_summary,
    summarize_conversation,
)
from personality_jelly.runtime.summary_schemas import ConversationSummaryDraft
from personality_jelly.storage import (
    ConversationRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class SummaryFakeProvider:
    name = "summary-fake"

    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.prompt = messages[-1].content
        return {
            "short_term_scene_state": "用户正在和角色进行现实会谈。",
            "user_memory_candidates": ["用户喜欢夜里写作。"],
            "relationship_memory_notes": ["用户希望角色记住写作偏好。"],
            "reflective_notes": ["不要把临时剧情写入 canon。"],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_summarize_conversation_updates_conversation_summary() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)
    provider = SummaryFakeProvider()

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="测试作品", source_type="markdown")
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="林霜",
            character_id="char_001",
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                source_work_id="sw_001",
                character_id="char_001",
                version_number=1,
                core_self="林霜谨慎敏锐。",
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="测试用户"))
        conversation = create_conversation(
            session,
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_001",
            conversation_id="conv_001",
        ).conversation
        MessageRepository(session).add(
            Message(
                id="msg_001",
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="请记住，我喜欢夜里写作。",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_002",
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="我记住了。",
            )
        )

        result = summarize_conversation(
            session,
            conversation_id=conversation.id,
            provider=provider,
            model_config=ModelConfig(model="summary-fake"),
        )
        session.commit()

    with session_factory() as session:
        updated = ConversationRepository(session).require("conv_001")

    assert "# Short-term Scene State" in result.conversation.summary
    assert "用户正在和角色进行现实会谈。" in result.conversation.summary
    assert "# User Memory Candidates" in result.conversation.summary
    assert "- 用户喜欢夜里写作。" in result.conversation.summary
    assert "# Relationship Memory Notes" in result.conversation.summary
    assert "- 用户希望角色记住写作偏好。" in result.conversation.summary
    assert "# Reflective Notes" in result.conversation.summary
    assert "- 不要把临时剧情写入 canon。" in result.conversation.summary
    assert updated.summary == result.conversation.summary
    assert "previous_summary:\nnone" in provider.prompt
    assert "summary_boundaries:" in provider.prompt
    assert "Temporary roleplay, jokes, and co-created fiction are not canon." in provider.prompt
    assert "- user: 请记住，我喜欢夜里写作。" in provider.prompt


def test_conversation_summary_schema_rejects_single_mixed_summary() -> None:
    try:
        ConversationSummaryDraft.model_validate({"summary": "mixed summary"})
    except ValueError as exc:
        assert "short_term_scene_state" in str(exc)
        assert "summary" in str(exc)
    else:
        raise AssertionError("Expected mixed single-field summary to fail validation")


def test_parse_layered_summary_returns_structured_layers() -> None:
    summary = "\n".join(
        [
            "# Short-term Scene State",
            "The user is planning a quiet scene.",
            "",
            "# User Memory Candidates",
            "- User prefers late-night writing.",
            "- User likes concise replies.",
            "",
            "# Relationship Memory Notes",
            "- User trusts the character with drafting.",
            "",
            "# Reflective Notes",
            "- Keep co-created fiction separate from canon.",
        ]
    )

    layers = parse_layered_summary(summary)

    assert layers.short_term_scene_state == "The user is planning a quiet scene."
    assert layers.user_memory_candidates == [
        "User prefers late-night writing.",
        "User likes concise replies.",
    ]
    assert layers.relationship_memory_notes == [
        "User trusts the character with drafting.",
    ]
    assert layers.reflective_notes == [
        "Keep co-created fiction separate from canon.",
    ]


def test_parse_layered_summary_handles_empty_and_legacy_summary() -> None:
    empty = parse_layered_summary(None)
    legacy = parse_layered_summary("Legacy unlayered summary.")

    assert empty.short_term_scene_state == "none"
    assert empty.user_memory_candidates == []
    assert legacy.short_term_scene_state == "Legacy unlayered summary."
    assert legacy.relationship_memory_notes == []
