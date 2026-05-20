from personality_jelly.domain import (
    Character,
    Conversation,
    ContextPackage,
    CriticReport,
    FailureCase,
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
    ContextPackageRepository,
    CriticReportRepository,
    FailureCaseRepository,
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
        conversations = ConversationRepository(session).list_for_user_character(
            "user_001",
            "char_001",
        )
        assert len(conversations) == 1
        assert ConversationRepository(session).list_recent(limit=1)[0].id == "conv_001"
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


def test_repositories_find_reusable_cli_records() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(
                id="sw_001",
                title="测试作品",
                source_type="markdown",
            )
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="林霜",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=1,
                core_self="林霜谨慎敏锐。",
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="demo-user"))
        ConversationRepository(session).add(
            Conversation(
                id="conv_001",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
                current_mode=InteractionMode.REALITY_CHAT,
            )
        )
        session.commit()

    with session_factory() as session:
        source_work = SourceWorkRepository(session).find_by_title("测试作品")
        character = CharacterRepository(session).find_by_source_work_and_name(
            "sw_001",
            "林霜",
        )
        user = UserRepository(session).find_by_display_name("demo-user")
        conversation = ConversationRepository(session).latest_for_user_character(
            "user_001",
            "char_001",
        )

    assert source_work.id == "sw_001"
    assert character.id == "char_001"
    assert user.id == "user_001"
    assert conversation.id == "conv_001"


def test_memory_repository_updates_content_and_status() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="用户喜欢清晨写作。",
            importance=0.7,
            reason="原始记录。",
        )
        repository = MemoryRepository(session)
        repository.add(memory)
        repository.update_content(
            "mem_001",
            content="用户喜欢夜里写作。",
            reason="用户修正了记忆。",
        )
        repository.update_status("mem_001", status=MemoryStatus.ARCHIVED)
        session.commit()

    with session_factory() as session:
        updated = MemoryRepository(session).require("mem_001")

    assert updated.content == "用户喜欢夜里写作。"
    assert updated.reason == "用户修正了记忆。"
    assert updated.status == "archived"


def test_memory_repository_reviews_candidate_memory() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.CANDIDATE,
            content="用户喜欢夜里写作。",
            importance=0.7,
            reason="semantic guard unavailable; queued for review",
        )
        reviewed = MemoryRepository(session).add(memory)
        reviewed = MemoryRepository(session).review_candidate(
            reviewed.id,
            status=MemoryStatus.ACCEPTED,
            reason="用户明确确认这是稳定偏好。",
        )
        session.commit()

    with session_factory() as session:
        stored = MemoryRepository(session).require("mem_001")

    assert reviewed.status == "accepted"
    assert stored.status == "accepted"
    assert "Review decision accepted" in stored.reason
    assert "用户明确确认这是稳定偏好。" in stored.reason


def test_failure_case_repository_lists_recent_and_by_conversation() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Failure Work", source_type="markdown")
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=1,
                core_self="Careful observer.",
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="tester"))
        ConversationRepository(session).add(
            Conversation(
                id="conv_001",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
                current_mode=InteractionMode.REALITY_CHAT,
            )
        )
        ContextPackageRepository(session).add(
            ContextPackage(
                id="ctx_001",
                conversation_id="conv_001",
                interaction_mode=InteractionMode.REALITY_CHAT,
                persona_version_id="pv_001",
                assembled_prompt="Prompt",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_user_001",
                conversation_id="conv_001",
                role=MessageRole.USER,
                content="Who are you?",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_assistant_001",
                conversation_id="conv_001",
                role=MessageRole.ASSISTANT,
                content="I am a generic assistant.",
                context_package_id="ctx_001",
            )
        )
        CriticReportRepository(session).add(
            CriticReport(
                id="cr_001",
                message_id="msg_assistant_001",
                ooc_risk="high",
                fact_risk="low",
                memory_risk="low",
                mode_risk="low",
                reasons=["Assistant broke character."],
                suggested_action="retry",
            )
        )
        FailureCaseRepository(session).add(
            FailureCase(
                id="fail_001",
                conversation_id="conv_001",
                user_message_id="msg_user_001",
                assistant_message_id="msg_assistant_001",
                context_package_id="ctx_001",
                critic_report_id="cr_001",
                category="retry",
                reason="Assistant broke character.",
                notes="Captured during retry.",
            )
        )
        session.commit()

    with session_factory() as session:
        repository = FailureCaseRepository(session)
        stored = repository.require("fail_001")
        recent = repository.list_recent(category="retry")
        by_conversation = repository.list_by_conversation("conv_001")

    assert stored.assistant_message_id == "msg_assistant_001"
    assert recent[0].id == "fail_001"
    assert by_conversation[0].reason == "Assistant broke character."

