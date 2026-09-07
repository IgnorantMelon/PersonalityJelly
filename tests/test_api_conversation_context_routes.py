from __future__ import annotations

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
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
from personality_jelly.runtime import create_conversation
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ContextPackageRepository,
    ConversationRepository,
    EvidenceRefRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def _client(tmp_path) -> TestClient:
    resources = create_database_resources(f"sqlite:///{tmp_path / 'api-conversation.db'}")
    _seed_conversation_context(resources.session_factory)
    app = create_app(settings=_settings(), database_resources=resources)
    return TestClient(app)


def test_list_conversations_returns_summary_items(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/conversations?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    assert payload["limit"] == 5
    assert payload["expansion"]["expanded"] == ["user", "character", "persona_version"]
    assert payload["items"][0]["id"] == "conv_001"
    assert payload["items"][0]["user"]["display_name"] == "demo-user"
    assert payload["items"][0]["character"]["canonical_name"] == "Lin Shuang"
    assert payload["items"][0]["persona_version"]["id"] == "persona_001"


def test_get_conversation_returns_detail_and_existing_expansions(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get(
            "/conversations/conv_001",
            params={"message_limit": 2, "include_memories": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "conv_001"
    assert payload["user_id"] == "user_001"
    assert payload["character_id"] == "char_001"
    assert payload["persona_version_id"] == "persona_001"
    assert payload["summary_layers"]["short_term_scene_state"] == "At the library."
    assert payload["summary_layers"]["user_memory_candidates"] == ["User likes tea."]
    assert [message["id"] for message in payload["messages"]] == ["msg_002", "msg_003"]
    assert payload["messages"][1]["context_package_id"] == "ctx_001"
    assert payload["memories"][0]["id"] == "mem_001"


def test_get_conversation_can_omit_link_expansions_and_messages(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get(
            "/conversations/conv_001",
            params={
                "message_limit": 0,
                "include_user": False,
                "include_character": False,
                "include_persona_version": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"] == []
    assert payload["user"] is None
    assert payload["character"] is None
    assert payload["persona_version"] is None


def test_get_context_package_defaults_to_ids_and_prompt(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/context-packages/ctx_001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "ctx_001"
    assert payload["conversation_id"] == "conv_001"
    assert payload["assembled_prompt"] == "assembled prompt"
    assert payload["expansion"]["mode"] == "ids"
    assert payload["claim_ids"] == ["claim_001"]
    assert payload["memory_ids"] == ["mem_001"]
    assert payload["retrieved_chunk_ids"] == ["chunk_001"]
    assert payload["claims"] == []
    assert payload["memories"] == []
    assert payload["retrieved_chunks"] == []


def test_get_context_package_expands_linked_details(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get(
            "/context-packages/ctx_001",
            params={
                "include_persona_version": True,
                "include_claims": True,
                "include_evidence": True,
                "include_evidence_chunks": True,
                "include_memories": True,
                "include_retrieved_chunks": True,
                "include_retrieved_chunk_text": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expansion"]["mode"] == "detail"
    assert payload["persona_version"]["id"] == "persona_001"
    assert payload["claims"][0]["id"] == "claim_001"
    assert payload["claims"][0]["evidence"][0]["id"] == "evidence_001"
    assert payload["claims"][0]["evidence"][0]["chunk"]["id"] == "chunk_001"
    assert payload["memories"][0]["id"] == "mem_001"
    assert payload["retrieved_chunks"][0]["id"] == "chunk_001"
    assert payload["retrieved_chunks"][0]["text"] == "Lin Shuang observes before acting."


def test_conversation_routes_return_not_found_envelopes(tmp_path) -> None:
    with _client(tmp_path) as client:
        conversation_response = client.get("/conversations/missing")
        context_response = client.get("/context-packages/missing")

    assert conversation_response.status_code == 404
    assert conversation_response.json()["error"]["code"] == "not_found"
    assert "ConversationORM 'missing' was not found" in conversation_response.json()["error"]["message"]
    assert context_response.status_code == 404
    assert context_response.json()["error"]["code"] == "not_found"
    assert "ContextPackageORM 'missing' was not found" in context_response.json()["error"]["message"]


def test_conversation_routes_reject_invalid_limits(tmp_path) -> None:
    with _client(tmp_path) as client:
        list_response = client.get("/conversations?limit=0")
        detail_response = client.get("/conversations/conv_001?message_limit=-1")

    assert list_response.status_code == 422
    assert list_response.json()["error"]["code"] == "validation_error"
    assert list_response.json()["error"]["details"]["errors"][0]["loc"] == ["query", "limit"]
    assert detail_response.status_code == 422
    assert detail_response.json()["error"]["code"] == "validation_error"
    assert detail_response.json()["error"]["details"]["errors"][0]["loc"] == [
        "query",
        "message_limit",
    ]


def _seed_conversation_context(session_factory) -> None:
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
        create_conversation(
            session,
            conversation_id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="persona_001",
        )
        conversation_repository = ConversationRepository(session)
        conversation = conversation_repository.require("conv_001")
        conversation_repository.update_summary(
            "conv_001",
            summary="\n".join(
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
            ),
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
