from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    Conversation,
    EvidenceRef,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ConversationRepository,
    EvidenceRefRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
)
from personality_jelly.storage.database import session_scope


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_character_list_filters_by_source_work(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/characters", params={"source_work_id": "sw_001"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert body["expansion"]["expanded"] == ["latest_persona", "counts"]
    assert [item["id"] for item in body["items"]] == ["char_001", "char_002"]
    assert body["items"][0]["source_work_id"] == "sw_001"
    assert body["items"][0]["latest_persona_version_id"] == "pv_002"
    assert body["items"][0]["claim_count"] == 2
    assert body["items"][0]["evidence_count"] == 3


def test_character_detail_expands_claim_evidence_and_chunks(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/characters/char_001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "char_001"
    assert body["source_work"]["id"] == "sw_001"
    assert body["latest_persona_version"]["id"] == "pv_002"
    assert [claim["id"] for claim in body["claims"]] == ["claim_001", "claim_002"]
    assert body["claims"][0]["evidence_ids"] == ["evidence_001", "evidence_002"]
    assert body["claims"][0]["evidence"][0]["chunk"]["id"] == "chunk_001"
    assert body["claims"][0]["evidence"][0]["chunk"]["text_preview"] == (
        "Lin Shuang observes before acting."
    )


def test_claim_list_filters_and_expands_evidence_chunks(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get(
            "/claims",
            params={
                "character_id": "char_001",
                "status": "verified",
                "claim_type": "personality",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert body["expansion"]["mode"] == "detail"
    claim = body["items"][0]
    assert claim["id"] == "claim_001"
    assert claim["status"] == "verified"
    assert claim["claim_type"] == "personality"
    assert [evidence["chunk_id"] for evidence in claim["evidence"]] == [
        "chunk_001",
        "chunk_002",
    ]
    assert claim["evidence"][1]["chunk"]["chapter_title"] == "Chapter One"


def test_claim_detail_expands_evidence_chunks(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/claims/claim_002")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "claim_002"
    assert body["evidence_ids"] == ["evidence_003"]
    assert body["evidence"][0]["chunk_id"] == "chunk_003"
    assert body["evidence"][0]["chunk"]["text_preview"] == (
        "She answers softly and chooses careful words."
    )


def test_memory_list_filters_by_user_character_scope_and_status(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get(
            "/memories",
            params={
                "user_id": "user_001",
                "character_id": "char_001",
                "scope": "relationship_memory",
                "status": "candidate",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert body["items"][0]["id"] == "mem_rel_001"
    assert body["items"][0]["scope"] == "relationship_memory"
    assert body["items"][0]["status"] == "candidate"


def test_memory_detail_preserves_scope_and_status(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/memories/mem_user_001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "mem_user_001"
    assert body["user_id"] == "user_001"
    assert body["character_id"] == "char_001"
    assert body["scope"] == "user_memory"
    assert body["status"] == "accepted"


def test_source_chunk_detail_returns_full_text(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/source-chunks/chunk_003")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "chunk_003"
    assert body["source_work_id"] == "sw_001"
    assert body["chapter_index"] == 2
    assert body["chapter_title"] == "Chapter Two"
    assert body["text"] == "She answers softly and chooses careful words."


def test_character_claim_memory_and_chunk_not_found_use_error_envelope(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        character_response = client.get("/characters/missing_character")
        claim_response = client.get("/claims/missing_claim")
        memory_response = client.get("/memories/missing_memory")
        chunk_response = client.get("/source-chunks/missing_chunk")

    for response in [character_response, claim_response, memory_response, chunk_response]:
        body = response.json()
        assert response.status_code == 404
        assert body["error"]["code"] == "not_found"
        assert body["error"]["trace_id"] is None


def test_invalid_query_enums_use_validation_error_envelope(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        claim_status_response = client.get(
            "/claims",
            params={"character_id": "char_001", "status": "approved"},
        )
        claim_type_response = client.get(
            "/claims",
            params={"character_id": "char_001", "claim_type": "mood"},
        )
        memory_scope_response = client.get(
            "/memories",
            params={
                "user_id": "user_001",
                "character_id": "char_001",
                "scope": "canon",
            },
        )
        memory_status_response = client.get(
            "/memories",
            params={
                "user_id": "user_001",
                "character_id": "char_001",
                "status": "approved",
            },
        )

    for response in [
        claim_status_response,
        claim_type_response,
        memory_scope_response,
        memory_status_response,
    ]:
        body = response.json()
        assert response.status_code == 422
        assert body["error"]["code"] == "validation_error"
        assert body["error"]["message"] == "Request validation failed"


def _seed_api_app(tmp_path):
    resources = create_database_resources(f"sqlite:///{tmp_path / 'api-character-memory.db'}")
    with session_scope(resources.session_factory) as session:
        _seed_records(session)
    return create_app(settings=_settings(), database_resources=resources)


def _seed_records(session) -> None:
    SourceWorkRepository(session).add(
        SourceWork(
            id="sw_001",
            title="Inspection Work",
            author="Test Author",
            source_type="markdown",
            created_at=NOW,
        )
    )
    SourceWorkRepository(session).add(
        SourceWork(
            id="sw_002",
            title="Other Work",
            source_type="markdown",
            created_at=NOW,
        )
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
            ),
            SourceChunk(
                id="chunk_002",
                source_work_id="sw_001",
                chapter_index=1,
                chapter_title="Chapter One",
                paragraph_index=2,
                text="She waits until everyone else has spoken.",
                char_start=36,
                char_end=57,
            ),
            SourceChunk(
                id="chunk_003",
                source_work_id="sw_001",
                chapter_index=2,
                chapter_title="Chapter Two",
                paragraph_index=1,
                text="She answers softly and chooses careful words.",
                char_start=58,
                char_end=104,
            ),
        ]
    )
    CharacterRepository(session).add(
        Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            aliases=["A-Shuang", "Observer"],
            created_at=NOW,
        )
    )
    CharacterRepository(session).add(
        Character(
            id="char_002",
            source_work_id="sw_001",
            canonical_name="Gu Yan",
            aliases=["Gu"],
            created_at=NOW,
        )
    )
    CharacterRepository(session).add(
        Character(
            id="char_other_work",
            source_work_id="sw_002",
            canonical_name="Other Work Character",
            created_at=NOW,
        )
    )
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="pv_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="Lin Shuang is cautious.",
            source_claim_ids=["claim_001"],
            created_at=NOW,
        )
    )
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="pv_002",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=2,
            core_self="Lin Shuang is cautious and soft-spoken.",
            source_claim_ids=["claim_001", "claim_002"],
            created_at=NOW,
        )
    )
    UserRepository(session).add(User(id="user_001", display_name="tester", created_at=NOW))
    UserRepository(session).add(User(id="user_002", display_name="other", created_at=NOW))
    ConversationRepository(session).add(
        Conversation(
            id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_002",
            current_mode=InteractionMode.REALITY_CHAT,
            created_at=NOW,
            updated_at=NOW,
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
            confidence=0.95,
            reasoning="Two source chunks show cautious observation.",
            created_by="test",
        )
    )
    CanonClaimRepository(session).add(
        CanonClaim(
            id="claim_002",
            source_work_id="sw_001",
            character_id="char_001",
            claim_type=ClaimType.SPEECH,
            content="Lin Shuang speaks softly and carefully.",
            status=ClaimStatus.CANDIDATE,
            confidence=0.75,
            created_by="test",
        )
    )
    EvidenceRefRepository(session).add_many(
        [
            EvidenceRef(
                id="evidence_001",
                claim_id="claim_001",
                chunk_id="chunk_001",
                excerpt="observes before acting",
                support_score=0.92,
            ),
            EvidenceRef(
                id="evidence_002",
                claim_id="claim_001",
                chunk_id="chunk_002",
                excerpt="waits until everyone else has spoken",
                support_score=0.86,
            ),
            EvidenceRef(
                id="evidence_003",
                claim_id="claim_002",
                chunk_id="chunk_003",
                excerpt="answers softly",
                support_score=0.8,
            ),
        ]
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_user_001",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="The user prefers late-night writing.",
            importance=0.8,
            reason="User stated a stable preference.",
            created_at=NOW,
        )
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_rel_001",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.RELATIONSHIP_MEMORY,
            status=MemoryStatus.CANDIDATE,
            content="Lin Shuang and the user are building trust.",
            importance=0.6,
            reason="Relationship tone changed over repeated turns.",
            created_at=NOW,
        )
    )
    MemoryRepository(session).add(
        Memory(
            id="mem_other_user",
            user_id="user_002",
            character_id="char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="Other user likes concise replies.",
            importance=0.4,
            reason="Other user stated preference.",
            created_at=NOW,
        )
    )
