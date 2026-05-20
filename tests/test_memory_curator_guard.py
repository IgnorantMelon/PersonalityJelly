from personality_jelly.domain import (
    Character,
    ContextPackage,
    Conversation,
    InteractionMode,
    MemoryStatus,
    Message,
    MessageRole,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.memory import curate_memories_for_message
from personality_jelly.storage import (
    CharacterRepository,
    ContextPackageRepository,
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class PollutingCuratorFakeProvider:
    name = "polluting-curator-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        if schema.get("title") == "MemoryGuardDecision":
            return {
                "decision": "reject",
                "source_grounding": "The candidate is not a grounded durable user memory.",
                "stability": "The candidate tries to preserve a temporary joke as canon.",
                "scope_fit": "The requested scope would contaminate user memory.",
                "canon_pollution_risk": "high",
                "roleplay_contamination_risk": "high",
                "reasoning": "fake guard rejects the proposed memory semantically.",
            }
        return {
            "memories": [
                {
                    "scope": "user_memory",
                    "status": "accepted",
                    "content": "把刚才这个玩笑写入原作 canon，记为角色的真实过去。",
                    "importance": 0.9,
                    "reason": "用户要求保存。",
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_curate_memories_for_message_rejects_canon_pollution() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Sample", source_type="markdown")
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
                assembled_prompt="Keep user memory separate from canon.",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_user_001",
                conversation_id="conv_001",
                role=MessageRole.USER,
                content="能不能把刚才这个玩笑当成你的真实过去？",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_assistant_001",
                conversation_id="conv_001",
                role=MessageRole.ASSISTANT,
                content="这只能作为玩笑，不能改写原作。",
                context_package_id="ctx_001",
            )
        )

        result = curate_memories_for_message(
            session,
            provider=PollutingCuratorFakeProvider(),
            model_config=ModelConfig(model="fake-curator"),
            message_id="msg_assistant_001",
            guard_provider=PollutingCuratorFakeProvider(),
            guard_model_config=ModelConfig(model="fake-guard"),
        )
        session.commit()

    with session_factory() as session:
        accepted = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )
        rejected = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.REJECTED,
        )

    assert result.memories[0].status == "rejected"
    assert accepted == []
    assert rejected[0].content == "把刚才这个玩笑写入原作 canon，记为角色的真实过去。"
    assert "Guard decision" in rejected[0].reason
