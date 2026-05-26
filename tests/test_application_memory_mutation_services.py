from __future__ import annotations

from datetime import datetime, timezone

import pytest

from personality_jelly.application import (
    CorrelationContext,
    LocalActorContext,
    ManualMemoryArchiveRequest,
    ManualMemoryEditRequest,
    ManualMemoryReviewRequest,
    archive_memory_workflow,
    edit_memory_workflow,
    review_memory_workflow,
)
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    Conversation,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ConversationRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


NOW = datetime(2026, 5, 26, 10, 0, tzinfo=timezone.utc)


def test_review_memory_workflow_accepts_candidate_with_audit_and_canon_boundary() -> None:
    session_factory = _seed_database()

    with session_factory() as session:
        result = review_memory_workflow(
            session,
            ManualMemoryReviewRequest(
                memory_id="mem_candidate",
                decision="accept",
                reason="User confirmed this is durable.",
                actor=_actor(),
                correlation=CorrelationContext(request_id="req_review"),
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
            ),
        )

        stored_memory = MemoryRepository(session).require("mem_candidate")
        stored_claim = CanonClaimRepository(session).require("claim_001")

    assert result.request_id == "req_review"
    assert result.workflow_id.startswith("wf_")
    assert result.workflow_type == "memory.review"
    assert result.status == "completed"
    assert result.ids.memory_id == "mem_candidate"
    assert result.ids.user_id == "user_001"
    assert result.memory.status == "accepted"
    assert result.audit_event.operation == "memory.review"
    assert result.audit_event.persistence == "payload_only"
    assert result.audit_event.before is not None
    assert result.audit_event.before["status"] == "candidate"
    assert result.audit_event.after is not None
    assert result.audit_event.after["status"] == "accepted"
    assert result.audit_event.metadata["request_id"] == "req_review"
    assert result.audit_event.metadata["workflow_status"] == "completed"
    assert result.audit_event.metadata["decision"] == "accept"
    assert stored_memory.status == "accepted"
    assert "Review decision accepted" in stored_memory.reason
    assert stored_claim.status == "verified"
    assert stored_claim.content == "Lin Shuang observes before acting."


def test_edit_memory_workflow_updates_content_reason_and_payload_audit() -> None:
    session_factory = _seed_database()

    with session_factory() as session:
        result = edit_memory_workflow(
            session,
            ManualMemoryEditRequest(
                memory_id="mem_accepted",
                content="User prefers writing after midnight.",
                reason="Manual correction after user clarification.",
                actor=_actor(),
                correlation=CorrelationContext(request_id="req_edit"),
                metadata={"source": "local-test"},
            ),
        )

        stored_memory = MemoryRepository(session).require("mem_accepted")

    assert result.workflow_type == "memory.edit"
    assert result.memory.content == "User prefers writing after midnight."
    assert result.memory.reason == "Manual correction after user clarification."
    assert result.audit_event.operation == "memory.edit"
    assert result.audit_event.before is not None
    assert result.audit_event.before["content"] == "User likes night writing."
    assert result.audit_event.after is not None
    assert result.audit_event.after["content"] == "User prefers writing after midnight."
    assert result.audit_event.metadata["source"] == "local-test"
    assert stored_memory.content == "User prefers writing after midnight."
    assert stored_memory.reason == "Manual correction after user clarification."


def test_archive_memory_workflow_requires_reason_and_archives_without_rewriting_content() -> None:
    session_factory = _seed_database()

    with session_factory() as session:
        result = archive_memory_workflow(
            session,
            ManualMemoryArchiveRequest(
                memory_id="mem_accepted",
                reason="User asked to remove stale memory.",
                actor=_actor(),
                correlation=CorrelationContext(request_id="req_archive"),
            ),
        )

        stored_memory = MemoryRepository(session).require("mem_accepted")

    assert result.workflow_type == "memory.archive"
    assert result.memory.status == "archived"
    assert result.memory.content == "User likes night writing."
    assert result.audit_event.operation == "memory.archive"
    assert result.audit_event.reason == "User asked to remove stale memory."
    assert result.audit_event.after is not None
    assert result.audit_event.after["status"] == "archived"
    assert stored_memory.status == "archived"
    assert stored_memory.content == "User likes night writing."


def test_manual_memory_workflows_reject_missing_actor_reason_and_related_mismatch() -> None:
    session_factory = _seed_database()

    with session_factory() as session:
        with pytest.raises(ValueError, match="local actor context is required"):
            review_memory_workflow(
                session,
                ManualMemoryReviewRequest(
                    memory_id="mem_candidate",
                    decision="accept",
                    reason="Review reason.",
                    actor=None,
                    correlation=CorrelationContext(request_id="req_no_actor"),
                ),
            )

        with pytest.raises(ValueError, match="reason is required"):
            edit_memory_workflow(
                session,
                ManualMemoryEditRequest(
                    memory_id="mem_accepted",
                    content="Updated content.",
                    actor=_actor(),
                    correlation=CorrelationContext(request_id="req_no_reason"),
                ),
            )

        with pytest.raises(ValueError, match="user_id must match memory user_id"):
            archive_memory_workflow(
                session,
                ManualMemoryArchiveRequest(
                    memory_id="mem_accepted",
                    reason="Archive reason.",
                    actor=_actor(user_id="user_other"),
                    correlation=CorrelationContext(request_id="req_wrong_actor"),
                ),
            )

        with pytest.raises(ValueError, match="character_id must match"):
            review_memory_workflow(
                session,
                ManualMemoryReviewRequest(
                    memory_id="mem_candidate",
                    decision="reject",
                    reason="Wrong character check.",
                    actor=_actor(),
                    correlation=CorrelationContext(request_id="req_wrong_character"),
                    character_id="char_other",
                ),
            )


def test_manual_memory_workflows_reject_not_found_and_invalid_status_transition() -> None:
    session_factory = _seed_database()

    with session_factory() as session:
        with pytest.raises(LookupError, match="missing_memory"):
            archive_memory_workflow(
                session,
                ManualMemoryArchiveRequest(
                    memory_id="missing_memory",
                    reason="Archive reason.",
                    actor=_actor(),
                    correlation=CorrelationContext(request_id="req_missing"),
                ),
            )

        with pytest.raises(ValueError, match="only candidate memories can be reviewed"):
            review_memory_workflow(
                session,
                ManualMemoryReviewRequest(
                    memory_id="mem_accepted",
                    decision="accept",
                    reason="Review non-candidate.",
                    actor=_actor(),
                    correlation=CorrelationContext(request_id="req_transition"),
                ),
            )

        with pytest.raises(ValueError, match="archived memories cannot be edited"):
            edit_memory_workflow(
                session,
                ManualMemoryEditRequest(
                    memory_id="mem_archived",
                    content="Updated archived memory.",
                    reason="Edit archived memory.",
                    actor=_actor(),
                    correlation=CorrelationContext(request_id="req_archived_edit"),
                ),
            )


def _actor(*, user_id: str = "user_001") -> LocalActorContext:
    return LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:reviewer",
        actor_label="Local reviewer",
        user_id=user_id,
        metadata={"entrypoint": "application-test"},
    )


def _seed_database():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(
                id="sw_001",
                title="Memory Mutation Work",
                source_type="markdown",
                created_at=NOW,
            )
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
                created_at=NOW,
            )
        )
        CharacterRepository(session).add(
            Character(
                id="char_other",
                source_work_id="sw_001",
                canonical_name="Other Character",
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
        UserRepository(session).add(User(id="user_001", display_name="tester", created_at=NOW))
        UserRepository(session).add(User(id="user_other", display_name="other", created_at=NOW))
        ConversationRepository(session).add(
            Conversation(
                id="conv_001",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
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
                confidence=0.9,
                created_by="test",
            )
        )
        MemoryRepository(session).add(
            Memory(
                id="mem_candidate",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.RELATIONSHIP_MEMORY,
                status=MemoryStatus.CANDIDATE,
                content="Lin Shuang and the user are building trust.",
                importance=0.7,
                reason="Guard queued this relationship note for review.",
                created_at=NOW,
            )
        )
        MemoryRepository(session).add(
            Memory(
                id="mem_accepted",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="User likes night writing.",
                importance=0.8,
                reason="User stated a stable preference.",
                created_at=NOW,
            )
        )
        MemoryRepository(session).add(
            Memory(
                id="mem_archived",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ARCHIVED,
                content="Old memory.",
                importance=0.2,
                reason="Previously archived.",
                created_at=NOW,
            )
        )
        session.commit()

    return session_factory
