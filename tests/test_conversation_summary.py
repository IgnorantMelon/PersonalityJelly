from personality_jelly.characters import create_character
from personality_jelly.domain import Message, MessageRole, PersonaVersion, SourceWork, User
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.runtime import create_conversation, summarize_conversation
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
        return {"summary": "用户说自己喜欢夜里写作，角色已经记住这个偏好。"}

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

    assert result.conversation.summary == "用户说自己喜欢夜里写作，角色已经记住这个偏好。"
    assert updated.summary == result.conversation.summary
    assert "previous_summary:\nnone" in provider.prompt
    assert "- user: 请记住，我喜欢夜里写作。" in provider.prompt
