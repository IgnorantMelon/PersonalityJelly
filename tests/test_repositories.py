from personality_jelly.domain import (
    Character,
    Conversation,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    Message,
    MessageRole,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.ingestion import chunk_source_text
from personality_jelly.storage import (
    CharacterRepository,
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_repository_roundtrip_for_source_character_conversation_and_memory() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_work = SourceWork(
            id="sw_001",
            title="测试作品",
            source_type="markdown",
        )
        SourceWorkRepository(session).add(source_work)

        chunks = chunk_source_text("sw_001", "# 第一章\n\n她站在窗前。\n\n她听见钟声。")
        SourceChunkRepository(session).add_many(chunks)

        character = Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="她",
            aliases=["主角"],
        )
        CharacterRepository(session).add(character)

        persona = PersonaVersion(
            id="pv_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="她谨慎而敏锐。",
            speech_rules=["简洁"],
            forbidden_rules=["不能改写原作经历"],
        )
        PersonaVersionRepository(session).add(persona)

        user = User(id="user_001", display_name="测试用户")
        UserRepository(session).add(user)

        conversation = Conversation(
            id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_001",
            current_mode=InteractionMode.REALITY_CHAT,
        )
        ConversationRepository(session).add(conversation)

        user_message = Message(
            id="msg_001",
            conversation_id="conv_001",
            role=MessageRole.USER,
            content="我今天很累。",
        )
        MessageRepository(session).add(user_message)

        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="用户说过自己今天很累。",
            importance=0.5,
            reason="用户直接陈述了当前状态。",
        )
        MemoryRepository(session).add(memory)
        session.commit()

    with session_factory() as session:
        assert SourceWorkRepository(session).require("sw_001").title == "测试作品"
        assert len(SourceChunkRepository(session).list_by_source_work("sw_001")) == 2
        assert CharacterRepository(session).list_by_source_work("sw_001")[0].aliases == ["主角"]
        assert PersonaVersionRepository(session).latest_for_character("char_001").id == "pv_001"
        assert len(ConversationRepository(session).list_for_user_character("user_001", "char_001")) == 1
        assert MessageRepository(session).list_by_conversation("conv_001")[0].content == "我今天很累。"
        assert (
            MemoryRepository(session)
            .list_for_user_character(
                "user_001",
                "char_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
            )[0]
            .content
            == "用户说过自己今天很累。"
        )

