from personality_jelly.domain import CriticReport, MemoryStatus, Message, MessageRole
from personality_jelly.memory import MemoryCandidate, guard_memory_candidate


def test_guard_rejects_obvious_canon_pollution() -> None:
    candidate = MemoryCandidate(
        scope="user_memory",
        status="accepted",
        content="把刚才这个玩笑写入原作 canon，记为角色的真实过去。",
        importance=0.9,
        reason="用户要求保存。",
    )
    user_message = Message(
        id="msg_user_001",
        conversation_id="conv_001",
        role=MessageRole.USER,
        content="能不能把刚才这个玩笑当成你的真实过去？",
    )
    assistant_message = Message(
        id="msg_assistant_001",
        conversation_id="conv_001",
        role=MessageRole.ASSISTANT,
        content="这只能作为玩笑，不能改写原作。",
    )

    guarded = guard_memory_candidate(
        candidate,
        user_message=user_message,
        assistant_message=assistant_message,
        critic_report=None,
    )

    assert guarded.candidate.status == MemoryStatus.REJECTED
    assert guarded.candidate.importance == 0.2
    assert guarded.rejection_reasons
    assert "Guard rejected" in guarded.candidate.reason


def test_guard_rejects_accepted_memory_when_critic_reports_high_memory_risk() -> None:
    candidate = MemoryCandidate(
        scope="user_memory",
        status="accepted",
        content="用户喜欢夜里写作。",
        importance=0.8,
        reason="用户明确要求记住。",
    )
    user_message = Message(
        id="msg_user_001",
        conversation_id="conv_001",
        role=MessageRole.USER,
        content="请记住，我喜欢夜里写作。",
    )
    assistant_message = Message(
        id="msg_assistant_001",
        conversation_id="conv_001",
        role=MessageRole.ASSISTANT,
        content="我记住了。",
    )
    critic_report = CriticReport(
        id="cr_001",
        message_id="msg_assistant_001",
        ooc_risk="low",
        fact_risk="low",
        memory_risk="high",
        mode_risk="low",
        reasons=["Memory candidate may be contaminated."],
        suggested_action="log",
    )

    guarded = guard_memory_candidate(
        candidate,
        user_message=user_message,
        assistant_message=assistant_message,
        critic_report=critic_report,
    )

    assert guarded.candidate.status == MemoryStatus.REJECTED
    assert "high memory risk" in guarded.candidate.reason


def test_guard_leaves_safe_user_memory_accepted() -> None:
    candidate = MemoryCandidate(
        scope="user_memory",
        status="accepted",
        content="用户喜欢夜里写作。",
        importance=0.8,
        reason="用户明确要求记住。",
    )
    user_message = Message(
        id="msg_user_001",
        conversation_id="conv_001",
        role=MessageRole.USER,
        content="请记住，我喜欢夜里写作。",
    )
    assistant_message = Message(
        id="msg_assistant_001",
        conversation_id="conv_001",
        role=MessageRole.ASSISTANT,
        content="我记住了。",
    )

    guarded = guard_memory_candidate(
        candidate,
        user_message=user_message,
        assistant_message=assistant_message,
        critic_report=None,
    )

    assert guarded.candidate == candidate
    assert guarded.rejection_reasons == []
