from __future__ import annotations

from personality_jelly.application import (
    ModelRoleBundle,
    ProviderRoleBundle,
    run_turn_workflow,
)
from personality_jelly.llm import ModelConfig
from personality_jelly.runtime import create_conversation, create_user
from personality_jelly.storage import (
    CharacterRepository,
    MemoryRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)
from tests.test_turn_orchestration import (
    AlwaysRetryCriticProvider,
    CompilerFakeProvider,
    CriticFakeProvider,
    MemoryCuratorFakeProvider,
    ReaderFakeProvider,
    RetryingRoleplayProvider,
    RoleplayFakeProvider,
    VerifierFakeProvider,
)
from personality_jelly.characters import create_character
from personality_jelly.domain import MemoryStatus
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.persona import compile_persona_version


def test_run_turn_workflow_returns_structured_ids_and_memory_statuses(tmp_path) -> None:
    session_factory = _seed_turn_workflow_database(tmp_path)

    with session_factory() as session:
        result = run_turn_workflow(
            session,
            conversation_id="conv_001",
            content="请记住，我喜欢在夜里写作。",
            provider_roles=ProviderRoleBundle(
                roleplay=RoleplayFakeProvider(),
                critic=CriticFakeProvider(),
                memory_curator=MemoryCuratorFakeProvider(),
            ),
            model_roles=ModelRoleBundle(
                roleplay=ModelConfig(model="fake-roleplay"),
                critic=ModelConfig(model="fake-critic"),
                memory_curator=ModelConfig(model="fake-memory"),
            ),
        )
        session.commit()

    with session_factory() as session:
        memories = MemoryRepository(session).list_for_user_character(
            "user_001",
            "char_001",
            status=MemoryStatus.ACCEPTED,
        )

    summary = result.summary
    assert summary.conversation_id == "conv_001"
    assert summary.user_message_id == result.runtime_result.user_message.id
    assert summary.assistant_message_id == result.runtime_result.assistant_message.id
    assert summary.context_package_id == result.runtime_result.context_package.id
    assert summary.interaction_mode == "reality_chat"
    assert summary.critic_report_id == result.runtime_result.critic_report.id
    assert summary.critic_action == "accept"
    assert summary.retry_count == 0
    assert summary.rejected_assistant_message_id is None
    assert summary.rejected_critic_report_id is None
    assert summary.failure_case_ids == []
    assert summary.memory_ids == [memories[0].id]
    assert summary.memories[0].status == "accepted"
    assert summary.model_dump(mode="json")["memories"][0]["id"] == memories[0].id


def test_run_turn_workflow_reports_retry_failure_ids(tmp_path) -> None:
    session_factory = _seed_turn_workflow_database(tmp_path)
    roleplay_provider = RetryingRoleplayProvider()
    critic_provider = AlwaysRetryCriticProvider()

    with session_factory() as session:
        result = run_turn_workflow(
            session,
            conversation_id="conv_001",
            content="Who are you?",
            provider_roles=ProviderRoleBundle(
                roleplay=roleplay_provider,
                critic=critic_provider,
            ),
            model_roles=ModelRoleBundle(
                roleplay=ModelConfig(model="fake-roleplay"),
                critic=ModelConfig(model="fake-critic"),
            ),
            retry_on_critic=True,
        )
        session.commit()

    summary = result.summary
    assert roleplay_provider.calls == 2
    assert critic_provider.calls == 2
    assert summary.retry_count == 1
    assert summary.rejected_assistant_message_id == result.runtime_result.rejected_assistant_message.id
    assert summary.rejected_critic_report_id == result.runtime_result.rejected_critic_report.id
    assert summary.critic_action == "retry"
    assert summary.failure_case_ids == [
        failure_case.id for failure_case in result.runtime_result.failure_cases
    ]
    assert len(summary.failure_case_ids) == 2
    assert summary.memories == []


def _seed_turn_workflow_database(tmp_path):
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="sample")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version
        user = create_user(session, user_id="user_001").user
        create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        )
        session.commit()
    return session_factory
