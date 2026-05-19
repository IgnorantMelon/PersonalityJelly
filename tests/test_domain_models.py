from pydantic import ValidationError

from personality_jelly.domain import (
    CanonClaim,
    ClaimStatus,
    ClaimType,
    Memory,
    MemoryScope,
    MemoryStatus,
    SourceWork,
)


def test_source_work_defaults_language_and_timestamp() -> None:
    source_work = SourceWork(id="sw_001", title="测试作品", source_type="markdown")

    assert source_work.language == "zh-CN"
    assert source_work.created_at.tzinfo is not None


def test_canon_claim_rejects_invalid_confidence() -> None:
    try:
        CanonClaim(
            id="claim_001",
            source_work_id="sw_001",
            character_id="char_001",
            claim_type=ClaimType.IDENTITY,
            content="她是主角。",
            status=ClaimStatus.CANDIDATE,
            confidence=1.5,
            created_by="reader",
        )
    except ValidationError as error:
        assert "less than or equal to 1" in str(error)
    else:
        raise AssertionError("Expected invalid confidence to fail validation.")


def test_memory_scope_keeps_user_memory_separate_from_canon() -> None:
    memory = Memory(
        id="mem_001",
        user_id="user_001",
        character_id="char_001",
        scope=MemoryScope.USER_MEMORY,
        status=MemoryStatus.ACCEPTED,
        content="用户喜欢晚上聊天。",
        importance=0.7,
        reason="用户明确要求记住。",
    )

    assert memory.scope == "user_memory"
    assert memory.character_id == "char_001"

