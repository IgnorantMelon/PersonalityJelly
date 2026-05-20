from personality_jelly.domain import CriticReport, InteractionMode, MemoryStatus, Message, MessageRole
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.memory import MemoryCandidate, guard_memory_candidate


class MemoryGuardFakeProvider:
    name = "memory-guard-fake"

    def __init__(self, decision: str) -> None:
        self.decision = decision

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "decision": self.decision,
            "source_grounding": "fake grounding assessment",
            "stability": "fake stability assessment",
            "scope_fit": "fake scope assessment",
            "canon_pollution_risk": "fake canon risk assessment",
            "roleplay_contamination_risk": "fake roleplay risk assessment",
            "reasoning": f"fake guard decision: {self.decision}",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


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
        interaction_mode=InteractionMode.REALITY_CHAT,
        critic_report=None,
        provider=MemoryGuardFakeProvider("reject"),
        model_config=ModelConfig(model="fake-guard"),
    )

    assert guarded.candidate.status == MemoryStatus.REJECTED
    assert guarded.candidate.importance == 0.2
    assert guarded.rejection_reasons
    assert "Guard decision" in guarded.candidate.reason


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
        interaction_mode=InteractionMode.REALITY_CHAT,
        critic_report=critic_report,
        provider=None,
        model_config=None,
    )

    assert guarded.candidate.status == MemoryStatus.REJECTED
    assert "high memory risk" in guarded.candidate.reason


def test_guard_queues_memory_without_semantic_guard_provider() -> None:
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
        interaction_mode=InteractionMode.REALITY_CHAT,
        critic_report=None,
        provider=None,
        model_config=None,
    )

    assert guarded.candidate.status == MemoryStatus.CANDIDATE
    assert guarded.decision == "candidate"
    assert "semantic guard unavailable" in guarded.candidate.reason


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
        interaction_mode=InteractionMode.REALITY_CHAT,
        critic_report=None,
        provider=MemoryGuardFakeProvider("accept"),
        model_config=ModelConfig(model="fake-guard"),
    )

    assert guarded.candidate == candidate
    assert guarded.rejection_reasons == []
