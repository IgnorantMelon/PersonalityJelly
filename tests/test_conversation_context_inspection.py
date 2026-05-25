from __future__ import annotations

from personality_jelly.application import (
    ContextPackageInspectionOptions,
    ConversationInspectionOptions,
    inspect_context_package,
    inspect_conversation,
    list_conversations,
)
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    ContextPackage,
    EvidenceRef,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    Message,
    MessageRole,
    PersonaVersion,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ConversationRepository,
    ContextPackageRepository,
    EvidenceRefRepository,
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
from personality_jelly.runtime import create_conversation


def test_inspect_conversation_returns_summary_layers_and_recent_messages() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = inspect_conversation(
            session,
            "conv_001",
            options=ConversationInspectionOptions(message_limit=2, include_memories=True),
        )

    payload = detail.model_dump(mode="json")
    assert payload["id"] == "conv_001"
    assert payload["user"]["display_name"] == "demo-user"
    assert payload["character"]["canonical_name"] == "Lin Shuang"
    assert payload["persona_version"]["version_number"] == 1
    assert payload["summary_layers"]["short_term_scene_state"] == "At the library."
    assert payload["summary_layers"]["user_memory_candidates"] == ["User likes tea."]
    assert [message["id"] for message in payload["messages"]] == ["msg_002", "msg_003"]
    assert payload["messages"][1]["context_package_id"] == "ctx_001"
    assert payload["memories"][0]["scope"] == "user_memory"


def test_inspect_conversation_can_omit_messages_and_link_expansion() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = inspect_conversation(
            session,
            "conv_001",
            options=ConversationInspectionOptions(
                message_limit=0,
                include_user=False,
                include_character=False,
                include_persona_version=False,
            ),
        )

    assert detail.user_id == "user_001"
    assert detail.character_id == "char_001"
    assert detail.persona_version_id == "persona_001"
    assert detail.messages == []
    assert detail.user is None
    assert detail.character is None
    assert detail.persona_version is None


def test_list_conversations_returns_linked_user_character_summaries() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        result = list_conversations(session, limit=5)

    assert result.total_count == 1
    assert result.limit == 5
    conversation = result.items[0]
    assert conversation.id == "conv_001"
    assert conversation.user is not None
    assert conversation.user.display_name == "demo-user"
    assert conversation.character is not None
    assert conversation.character.canonical_name == "Lin Shuang"
    assert conversation.persona_version is not None
    assert conversation.persona_version.id == "persona_001"


def test_inspect_context_package_defaults_to_ids_and_prompt() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = inspect_context_package(session, "ctx_001")

    payload = detail.model_dump(mode="json")
    assert payload["id"] == "ctx_001"
    assert payload["persona_version_id"] == "persona_001"
    assert payload["claim_ids"] == ["claim_001"]
    assert payload["memory_ids"] == ["mem_001"]
    assert payload["retrieved_chunk_ids"] == ["chunk_001"]
    assert payload["assembled_prompt"] == "assembled prompt"
    assert payload["expansion"]["mode"] == "ids"
    assert payload["claims"] == []
    assert payload["memories"] == []
    assert payload["retrieved_chunks"] == []


def test_inspect_context_package_expands_linked_details() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = inspect_context_package(
            session,
            "ctx_001",
            options=ContextPackageInspectionOptions(
                include_persona_version=True,
                include_claims=True,
                include_evidence=True,
                include_evidence_chunks=True,
                include_memories=True,
                include_retrieved_chunks=True,
                include_retrieved_chunk_text=True,
            ),
        )

    payload = detail.model_dump(mode="json")
    assert payload["expansion"]["mode"] == "detail"
    assert payload["persona_version"]["id"] == "persona_001"
    assert payload["claims"][0]["evidence_ids"] == ["evidence_001"]
    assert payload["claims"][0]["evidence"][0]["chunk"]["id"] == "chunk_001"
    assert payload["memories"][0]["id"] == "mem_001"
    assert payload["retrieved_chunks"][0]["id"] == "chunk_001"
    assert payload["retrieved_chunks"][0]["text"] == "Lin Shuang observes before acting."


def test_inspect_conversation_rejects_negative_message_limit() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        try:
            inspect_conversation(
                session,
                "conv_001",
                options=ConversationInspectionOptions(message_limit=-1),
            )
        except ValueError as exc:
            assert "message_limit must be 0 or greater" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def _seed_inspection_database():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Novel", source_type="markdown")
        )
        SourceChunkRepository(session).add_many(
            [
                SourceChunk(
                    id="chunk_001",
                    source_work_id="sw_001",
                    chapter_index=1,
                    chapter_title="Chapter One",
                    paragraph_index=1,
                    text="Lin Shuang observes before acting.",
                    char_start=0,
                    char_end=35,
                )
            ]
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
                aliases=["A-Shuang"],
            )
        )
        CanonClaimRepository(session).add(
            CanonClaim(
                id="claim_001",
                source_work_id="sw_001",
                character_id="char_001",
                claim_type=ClaimType.PERSONALITY,
                content="Lin Shuang observes before acting.",
                status=ClaimStatus.VERIFIED,
                confidence=0.9,
                reasoning="Supported by source.",
                created_by="reader",
            )
        )
        EvidenceRefRepository(session).add(
            EvidenceRef(
                id="evidence_001",
                claim_id="claim_001",
                chunk_id="chunk_001",
                excerpt="observes before acting",
                support_score=0.95,
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="persona_001",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=1,
                core_self="Careful observer.",
                source_claim_ids=["claim_001"],
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="demo-user"))
        conversation = create_conversation(
            session,
            conversation_id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="persona_001",
        ).conversation
        conversation = conversation.model_copy(
            update={
                "summary": "\n".join(
                    [
                        "# Short-term Scene State",
                        "At the library.",
                        "",
                        "# User Memory Candidates",
                        "- User likes tea.",
                        "",
                        "# Relationship Memory Notes",
                        "- Trust is growing.",
                        "",
                        "# Reflective Notes",
                        "- Keep canon separate.",
                    ]
                )
            }
        )
        # Repository update_summary keeps timestamps consistent without changing other fields.
        ConversationRepository(session).update_summary(
            conversation.id,
            summary=conversation.summary or "",
            updated_at=conversation.updated_at,
        )
        MemoryRepository(session).add(
            Memory(
                id="mem_001",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="User likes tea.",
                importance=0.8,
                reason="User stated preference.",
            )
        )
        ContextPackageRepository(session).add(
            ContextPackage(
                id="ctx_001",
                conversation_id="conv_001",
                interaction_mode=InteractionMode.REALITY_CHAT,
                persona_version_id="persona_001",
                claim_ids=["claim_001"],
                memory_ids=["mem_001"],
                retrieved_chunk_ids=["chunk_001"],
                assembled_prompt="assembled prompt",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_001",
                conversation_id="conv_001",
                role=MessageRole.USER,
                content="Hello.",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_002",
                conversation_id="conv_001",
                role=MessageRole.USER,
                content="Please remember I like tea.",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_003",
                conversation_id="conv_001",
                role=MessageRole.ASSISTANT,
                content="I will remember.",
                context_package_id="ctx_001",
            )
        )
        session.commit()
    return session_factory
