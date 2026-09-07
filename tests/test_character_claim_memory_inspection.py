from __future__ import annotations

from datetime import datetime, timezone

from personality_jelly.application import (
    get_character_detail,
    get_claim_detail,
    get_memory_detail,
    get_source_chunk_detail,
    list_characters,
    list_claims,
    list_memories,
)
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
    create_all,
    create_database_engine,
    create_session_factory,
)


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_character_list_filters_by_source_work_and_includes_counts() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        result = list_characters(session, source_work_id="sw_001")

    assert result.total_count == 1
    assert result.expansion.mode == "summary"
    assert result.expansion.expanded == ["latest_persona", "counts"]
    character = result.items[0]
    assert character.id == "char_001"
    assert character.source_work_id == "sw_001"
    assert character.latest_persona_version_id == "pv_002"
    assert character.claim_count == 2
    assert character.evidence_count == 3


def test_character_detail_includes_source_persona_claim_and_evidence_counts() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = get_character_detail(session, "char_001", expand_evidence_chunks=True)

    assert detail.id == "char_001"
    assert detail.source_work_id == "sw_001"
    assert detail.aliases == ["A-Shuang", "Observer"]
    assert detail.source_work is not None
    assert detail.source_work.id == "sw_001"
    assert detail.latest_persona_version_id == "pv_002"
    assert detail.latest_persona_version is not None
    assert detail.latest_persona_version.id == "pv_002"
    assert detail.claim_count == 2
    assert detail.evidence_count == 3
    assert [claim.id for claim in detail.claims] == ["claim_001", "claim_002"]

    first_claim = detail.claims[0]
    assert first_claim.evidence_ids == ["evidence_001", "evidence_002"]
    assert first_claim.evidence[0].chunk_id == "chunk_001"
    assert first_claim.evidence[0].excerpt == "observes before acting"
    assert first_claim.evidence[0].support_score == 0.92
    assert first_claim.evidence[0].chunk is not None
    assert first_claim.evidence[0].chunk.text_preview == "Lin Shuang observes before acting."


def test_claim_list_filters_and_can_expand_evidence_without_chunks() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        result = list_claims(
            session,
            "char_001",
            status=ClaimStatus.VERIFIED,
            claim_type=ClaimType.PERSONALITY,
            expand_evidence=True,
            expand_chunks=False,
        )

    assert result.total_count == 1
    assert result.expansion.mode == "summary"
    claim = result.items[0]
    assert claim.id == "claim_001"
    assert claim.status == "verified"
    assert claim.claim_type == "personality"
    assert claim.evidence_ids == ["evidence_001", "evidence_002"]
    assert [evidence.chunk_id for evidence in claim.evidence] == ["chunk_001", "chunk_002"]
    assert claim.evidence[0].chunk is None


def test_claim_detail_includes_evidence_chunk_summaries() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = get_claim_detail(session, "claim_002")

    assert detail.id == "claim_002"
    assert detail.evidence_ids == ["evidence_003"]
    assert detail.evidence[0].chunk_id == "chunk_003"
    assert detail.evidence[0].chunk is not None
    assert detail.evidence[0].chunk.chapter_title == "Chapter Two"
    assert detail.evidence[0].chunk.text_preview == "She answers softly and chooses careful words."


def test_source_chunk_detail_returns_full_text_and_location_fields() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = get_source_chunk_detail(session, "chunk_003")

    assert detail.id == "chunk_003"
    assert detail.source_work_id == "sw_001"
    assert detail.chapter_index == 2
    assert detail.chapter_title == "Chapter Two"
    assert detail.paragraph_index == 1
    assert detail.char_start == 58
    assert detail.char_end == 104
    assert detail.text == "She answers softly and chooses careful words."


def test_memory_list_filters_by_user_character_scope_and_status() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        user_memories = list_memories(
            session,
            "user_001",
            "char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
        )
        relationship_memories = list_memories(
            session,
            "user_001",
            "char_001",
            scope=MemoryScope.RELATIONSHIP_MEMORY,
            status=MemoryStatus.CANDIDATE,
        )
        other_user_memories = list_memories(session, "user_002", "char_001")

    assert user_memories.total_count == 1
    assert user_memories.items[0].id == "mem_user_001"
    assert user_memories.items[0].scope == "user_memory"
    assert user_memories.items[0].status == "accepted"

    assert relationship_memories.total_count == 1
    assert relationship_memories.items[0].id == "mem_rel_001"
    assert relationship_memories.items[0].scope == "relationship_memory"
    assert relationship_memories.items[0].status == "candidate"

    assert other_user_memories.total_count == 1
    assert other_user_memories.items[0].id == "mem_other_user"


def test_memory_detail_returns_structured_scope_and_status() -> None:
    session_factory = _seed_inspection_database()

    with session_factory() as session:
        detail = get_memory_detail(session, "mem_rel_001")

    assert detail.user_id == "user_001"
    assert detail.character_id == "char_001"
    assert detail.conversation_id == "conv_001"
    assert detail.scope == "relationship_memory"
    assert detail.status == "candidate"
    assert detail.content == "Lin Shuang and the user are building trust."


def _seed_inspection_database():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(
                id="sw_001",
                title="Inspection Work",
                author="Test Author",
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
        session.commit()

    return session_factory
