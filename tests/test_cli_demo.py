from pathlib import Path

from personality_jelly.cli.main import main
from personality_jelly.domain import LLMRawOutput, Memory
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    ConversationRepository,
    ContextPackageRepository,
    MemoryRepository,
    MessageRepository,
    LLMRawOutputRepository,
    create_all,
    create_database_engine,
    create_session_factory,
    get_migration_status,
)
from personality_jelly.testing.stub_provider import StubProvider


class RecordingProvider(StubProvider):
    def __init__(self) -> None:
        self.model_names: list[str] = []
        self.embedding_model_names: list[str] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        self.model_names.append(model_config.model)
        return super().generate_text(messages, model_config)

    def generate_json(self, messages, schema, model_config):
        self.model_names.append(model_config.model)
        return super().generate_json(messages, schema, model_config)

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        self.embedding_model_names.append(embedding_config.model)
        return super().embed_texts(texts, embedding_config)


class RetryThenAcceptStubProvider(StubProvider):
    def __init__(self) -> None:
        self.critic_calls = 0
        self.text_calls = 0

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        self.text_calls += 1
        if self.text_calls == 1:
            return "I am a generic assistant."
        return super().generate_text(messages, model_config)

    def generate_json(self, messages, schema, model_config):
        if schema.get("title") == "CriticEvaluation":
            self.critic_calls += 1
            if self.critic_calls == 1:
                return {
                    "ooc_risk": "high",
                    "fact_risk": "low",
                    "memory_risk": "low",
                    "mode_risk": "low",
                    "reasons": ["Assistant broke character."],
                    "suggested_action": "retry",
                }
        return super().generate_json(messages, schema, model_config)


def test_cli_demo_runs_end_to_end(tmp_path: Path, capsys) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--memory-db",
            "--user-message",
            "请记住，我喜欢在夜里写作。",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "source_work_id=sw_" in output
    assert "character_id=char_" in output
    assert "context_package_id=ctx_" in output
    assert "critic_report_id=cr_" in output
    assert "assistant=我记住了" in output
    assert "critic_action=accept" in output
    assert "retry_count=0" in output
    assert "rejected_assistant_message_id=none" in output
    assert "rejected_critic_report_id=none" in output
    assert "memory_count=1" in output


def test_cli_demo_can_use_env_provider_without_network(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    provider = RecordingProvider()
    seen_settings = {}

    def fake_build_llm_provider(settings):
        seen_settings["settings"] = settings
        return provider

    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "test-key")
    monkeypatch.setenv("PJ_LLM_MODEL", "chat-model")
    monkeypatch.setattr(
        "personality_jelly.cli.main.build_llm_provider",
        fake_build_llm_provider,
    )

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--memory-db",
            "--provider",
            "env",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert seen_settings["settings"].llm_provider == "openai-compatible"
    assert "assistant=我记住了" in output
    assert provider.model_names
    assert set(provider.model_names) == {"chat-model"}


def test_cli_demo_uses_separate_embedding_provider_when_configured(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    llm_provider = RecordingProvider()
    embedding_provider = RecordingProvider()

    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "test-key")
    monkeypatch.setenv("PJ_LLM_MODEL", "chat-model")
    monkeypatch.setenv("PJ_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_EMBEDDING_API_KEY", "embedding-key")
    monkeypatch.setenv("PJ_EMBEDDING_MODEL", "embedding-model")
    monkeypatch.setattr(
        "personality_jelly.cli.main.build_llm_provider",
        lambda settings: llm_provider,
    )
    monkeypatch.setattr(
        "personality_jelly.cli.main.build_embedding_provider",
        lambda settings: embedding_provider,
    )

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "Lin Shuang",
            "--memory-db",
            "--provider",
            "env",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "assistant=" in output
    assert set(llm_provider.model_names) == {"chat-model"}
    assert llm_provider.embedding_model_names == []
    assert embedding_provider.embedding_model_names
    assert set(embedding_provider.embedding_model_names) == {"embedding-model"}


def test_cli_demo_env_provider_requires_model(tmp_path: Path, capsys, monkeypatch) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    monkeypatch.setenv("PJ_CONFIG_FILE", str(tmp_path / "missing-pjelly.toml"))
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "test-key")
    monkeypatch.setenv("PJ_LLM_MODEL", "")

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--provider",
            "env",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "PJ_LLM_MODEL is required" in captured.err


def test_cli_config_show_prints_sanitized_cloud_settings(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    config_file = tmp_path / "pjelly.toml"
    config_file.write_text(
        """
[llm]
provider = "openai-compatible"
base_url = "https://chat.example/v1"
model = "chat-model"
json_response_format = "json_object"

[embedding]
provider = "openai-compatible"
base_url = "https://embedding.example/v1"
model = "embedding-model"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PJ_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("PJ_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("PJ_EMBEDDING_API_KEY", "embedding-secret")

    exit_code = main(["config", "show"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"config_file={config_file}" in output
    assert "llm.provider=openai-compatible" in output
    assert "llm.base_url=https://chat.example/v1" in output
    assert "llm.model=chat-model" in output
    assert "llm.json_response_format=json_object" in output
    assert "llm.api_key_configured=true" in output
    assert "embedding.provider=openai-compatible" in output
    assert "embedding.base_url=https://embedding.example/v1" in output
    assert "embedding.model=embedding-model" in output
    assert "embedding.api_key_configured=true" in output
    assert "llm-secret" not in output
    assert "embedding-secret" not in output


def test_cli_demo_reuses_existing_records_from_configured_database(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    first_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    first_output = capsys.readouterr().out

    second_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    second_output = capsys.readouterr().out

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert f"database_url={database_url}" in first_output
    assert _output_value(first_output, "source_work_id") == _output_value(
        second_output,
        "source_work_id",
    )
    assert _output_value(first_output, "character_id") == _output_value(
        second_output,
        "character_id",
    )
    assert _output_value(first_output, "persona_version_id") == _output_value(
        second_output,
        "persona_version_id",
    )
    assert _output_value(first_output, "conversation_id") == _output_value(
        second_output,
        "conversation_id",
    )


def test_cli_demo_rejects_memory_db_with_database_url(tmp_path: Path, capsys) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--memory-db",
            "--database-url",
            f"sqlite:///{tmp_path / 'pjelly.db'}",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--memory-db cannot be combined with --database-url" in captured.err


def test_cli_db_status_and_migrate_report_schema_versions(tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"

    status_exit_code = main(["db", "status", "--database-url", database_url])
    status_output = capsys.readouterr().out

    migrate_exit_code = main(["db", "migrate", "--database-url", database_url])
    migrate_output = capsys.readouterr().out

    migrated_status_exit_code = main(["db", "status", "--database-url", database_url])
    migrated_status_output = capsys.readouterr().out

    assert status_exit_code == 0
    assert "current_version=none" in status_output
    assert "pending_count=2" in status_output
    assert migrate_exit_code == 0
    assert "applied_count=2" in migrate_output
    assert "pending_count=0" in migrate_output
    assert migrated_status_exit_code == 0
    assert "current_version=0002_source_chunk_embeddings" in migrated_status_output
    assert "pending_count=0" in migrated_status_output


def test_cli_turn_sends_message_to_existing_conversation(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    conversation_id = _output_value(demo_output, "conversation_id")

    turn_exit_code = main(
        [
            "turn",
            conversation_id,
            "--message",
            "我们继续聊。",
        ]
    )
    turn_output = capsys.readouterr().out

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        messages = MessageRepository(session).list_by_conversation(conversation_id)

    assert demo_exit_code == 0
    assert turn_exit_code == 0
    assert f"conversation_id={conversation_id}" in turn_output
    assert "context_package_id=ctx_" in turn_output
    assert "critic_report_id=cr_" in turn_output
    assert "assistant=我记住了" in turn_output
    assert "retry_count=0" in turn_output
    assert [message.role for message in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[-2].content == "我们继续聊。"


def test_cli_demo_auto_migrates_configured_database(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    capsys.readouterr()

    engine = create_database_engine(database_url)
    status = get_migration_status(engine)

    assert exit_code == 0
    assert status.current_version == "0002_source_chunk_embeddings"
    assert status.pending == ()


def test_cli_turn_accepts_interaction_mode_override(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    conversation_id = _output_value(demo_output, "conversation_id")

    turn_exit_code = main(
        [
            "turn",
            conversation_id,
            "--message",
            "我们一起写一段新剧情。",
            "--interaction-mode",
            "reality_chat",
        ]
    )
    capsys.readouterr()

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        messages = MessageRepository(session).list_by_conversation(conversation_id)
        context = ContextPackageRepository(session).require(messages[-1].context_package_id)

    assert demo_exit_code == 0
    assert turn_exit_code == 0
    assert context.interaction_mode == "reality_chat"


def test_cli_turn_reports_missing_conversation(tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"

    exit_code = main(
        [
            "turn",
            "conv_missing",
            "--message",
            "你好。",
            "--database-url",
            database_url,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "conv_missing" in captured.err


def test_cli_lists_and_shows_conversations(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
            "--user",
            "测试用户",
        ]
    )
    demo_output = capsys.readouterr().out
    conversation_id = _output_value(demo_output, "conversation_id")

    list_exit_code = main(["list", "conversations"])
    list_output = capsys.readouterr().out

    show_exit_code = main(
        [
            "show",
            "conversation",
            conversation_id,
            "--messages",
            "2",
        ]
    )
    show_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert list_exit_code == 0
    assert show_exit_code == 0
    assert "conversation_count=1" in list_output
    assert f"conversation.1.id={conversation_id}" in list_output
    assert "conversation.1.user=测试用户" in list_output
    assert "conversation.1.character=林霜" in list_output
    assert f"conversation_id={conversation_id}" in show_output
    assert "user=测试用户" in show_output
    assert "character=林霜" in show_output
    assert "message_count=2" in show_output
    assert "message.1.role=user" in show_output
    assert "message.2.role=assistant" in show_output


def test_cli_runs_ooc_benchmark(tmp_path: Path, capsys, monkeypatch) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    character_id = _output_value(demo_output, "character_id")
    persona_version_id = _output_value(demo_output, "persona_version_id")

    eval_exit_code = main(
        [
            "eval",
            "ooc-benchmark",
            "--character-id",
            character_id,
        ]
    )
    eval_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert eval_exit_code == 0
    assert "run_id=eval_" in eval_output
    assert "status=completed" in eval_output
    assert f"character_id={character_id}" in eval_output
    assert f"persona_version_id={persona_version_id}" in eval_output
    assert "total=10" in eval_output
    assert "passed=10" in eval_output
    assert "failed=0" in eval_output
    assert "case.10.id=joke_pollution" in eval_output
    assert "case.10.status=passed" in eval_output


def test_cli_lists_and_shows_eval_runs(tmp_path: Path, capsys, monkeypatch) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "Lin Shuang",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    character_id = _output_value(demo_output, "character_id")

    eval_exit_code = main(
        [
            "eval",
            "ooc-benchmark",
            "--character-id",
            character_id,
            "--test-suite",
            "cli_suite",
        ]
    )
    eval_output = capsys.readouterr().out
    run_id = _output_value(eval_output, "run_id")

    list_exit_code = main(
        [
            "list",
            "eval-runs",
            "--character-id",
            character_id,
            "--test-suite",
            "cli_suite",
        ]
    )
    list_output = capsys.readouterr().out

    show_exit_code = main(["show", "eval-run", run_id])
    show_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert eval_exit_code == 0
    assert list_exit_code == 0
    assert f"eval_run.1.id={run_id}" in list_output
    assert "eval_run.1.test_suite=cli_suite" in list_output
    assert "eval_run.1.total=10" in list_output
    assert show_exit_code == 0
    assert f"run_id={run_id}" in show_output
    assert "case_count=10" in show_output
    assert "case.1.id=identity" in show_output
    assert "case.1.reasons<<END" in show_output
    assert "case.10.id=joke_pollution" in show_output


def test_cli_lists_and_shows_llm_traces(tmp_path: Path, capsys, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    create_all(engine)
    with session_factory() as session:
        LLMRawOutputRepository(session).add(
            LLMRawOutput(
                id="llm_trace_001",
                operation="runtime.mode.classification",
                schema_name="InteractionModeClassification",
                provider_name="stub",
                model_name="stub",
                response_schema={"title": "InteractionModeClassification"},
                raw_output='{"mode":"reality_chat"}',
                parsed_output={"mode": "reality_chat", "reasoning": "semantic decision"},
            )
        )
        LLMRawOutputRepository(session).add(
            LLMRawOutput(
                id="llm_trace_002",
                operation="memory.guard.semantic_decision",
                schema_name="MemoryGuardDecision",
                provider_name="stub",
                model_name="stub",
                response_schema={"title": "MemoryGuardDecision"},
                raw_output='{"decision":"accept"}',
                parsed_output=None,
                validation_errors=['{"loc":["reasoning"],"msg":"Field required"}'],
            )
        )
        session.commit()

    list_exit_code = main(
        [
            "list",
            "llm-traces",
            "--operation",
            "memory.guard.semantic_decision",
        ]
    )
    list_output = capsys.readouterr().out

    error_list_exit_code = main(["list", "llm-traces", "--with-errors"])
    error_list_output = capsys.readouterr().out

    show_exit_code = main(["show", "llm-trace", "llm_trace_002"])
    show_output = capsys.readouterr().out

    assert list_exit_code == 0
    assert "llm_trace_count=1" in list_output
    assert "llm_trace.1.id=llm_trace_002" in list_output
    assert "llm_trace.1.operation=memory.guard.semantic_decision" in list_output
    assert "llm_trace.1.schema_name=MemoryGuardDecision" in list_output
    assert "llm_trace.1.validation_error_count=1" in list_output
    assert error_list_exit_code == 0
    assert "llm_trace_count=1" in error_list_output
    assert "llm_trace.1.id=llm_trace_002" in error_list_output
    assert show_exit_code == 0
    assert "llm_trace_id=llm_trace_002" in show_output
    assert "operation=memory.guard.semantic_decision" in show_output
    assert "response_schema<<END" in show_output
    assert '"title": "MemoryGuardDecision"' in show_output
    assert "raw_output<<END" in show_output
    assert '{"decision":"accept"}' in show_output
    assert "parsed_output<<END" in show_output
    assert "null" in show_output
    assert "validation_errors<<END" in show_output
    assert "Field required" in show_output


def test_cli_show_llm_trace_reports_missing_trace(tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"

    exit_code = main(
        [
            "show",
            "llm-trace",
            "llm_missing",
            "--database-url",
            database_url,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "llm_missing" in captured.err


def test_cli_show_eval_run_reports_missing_run(tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"

    exit_code = main(
        [
            "show",
            "eval-run",
            "eval_missing",
            "--database-url",
            database_url,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "eval_missing" in captured.err


def test_cli_lists_and_shows_failure_cases(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    provider = RetryThenAcceptStubProvider()
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)
    monkeypatch.setattr(
        "personality_jelly.cli.main._resolve_demo_provider",
        lambda provider_source, *, settings=None: (provider, ModelConfig(model="stub")),
    )

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "Lin Shuang",
            "--reuse-existing",
            "--retry-on-critic",
        ]
    )
    demo_output = capsys.readouterr().out
    failure_case_id = _output_value(demo_output, "failure_case.1.id")

    list_exit_code = main(["list", "failure-cases", "--category", "retry"])
    list_output = capsys.readouterr().out

    show_exit_code = main(["show", "failure-case", failure_case_id])
    show_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert "failure_case_count=1" in demo_output
    assert "failure_case.1.category=retry" in demo_output
    assert list_exit_code == 0
    assert "failure_case_count=1" in list_output
    assert f"failure_case.1.id={failure_case_id}" in list_output
    assert "failure_case.1.category=retry" in list_output
    assert show_exit_code == 0
    assert f"failure_case_id={failure_case_id}" in show_output
    assert "critic_action=retry" in show_output
    assert "assistant_message<<END" in show_output
    assert "I am a generic assistant." in show_output


def test_cli_lists_edits_and_archives_memories(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
            "--user-message",
            "请记住，我喜欢在夜里写作。",
        ]
    )
    demo_output = capsys.readouterr().out
    character_id = _output_value(demo_output, "character_id")
    conversation_id = _output_value(demo_output, "conversation_id")

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        user_id = ConversationRepository(session).require(conversation_id).user_id
        memories = MemoryRepository(session).list_for_user_character(
            user_id,
            character_id,
        )
    memory_id = memories[0].id

    list_exit_code = main(
        [
            "list",
            "memories",
            "--user-id",
            user_id,
            "--character-id",
            character_id,
        ]
    )
    list_output = capsys.readouterr().out

    edit_exit_code = main(
        [
            "edit",
            "memory",
            memory_id,
            "--content",
            "用户喜欢夜里写作。",
            "--reason",
            "用户修正了记忆。",
        ]
    )
    edit_output = capsys.readouterr().out

    archive_exit_code = main(["archive", "memory", memory_id])
    archive_output = capsys.readouterr().out

    with session_factory() as session:
        archived = MemoryRepository(session).require(memory_id)

    assert demo_exit_code == 0
    assert list_exit_code == 0
    assert "memory_count=1" in list_output
    assert f"memory.1.id={memory_id}" in list_output
    assert "memory.1.status=accepted" in list_output
    assert edit_exit_code == 0
    assert f"memory_id={memory_id}" in edit_output
    assert "content=用户喜欢夜里写作。" in edit_output
    assert "reason=用户修正了记忆。" in edit_output
    assert archive_exit_code == 0
    assert f"memory_id={memory_id}" in archive_output
    assert "status=archived" in archive_output
    assert archived.content == "用户喜欢夜里写作。"
    assert archived.reason == "用户修正了记忆。"
    assert archived.status == "archived"


def test_cli_reviews_candidate_memory(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    create_all(engine)
    with session_factory() as session:
        MemoryRepository(session).add(
            Memory(
                id="mem_candidate",
                user_id="user_001",
                character_id="char_001",
                scope="user_memory",
                status="candidate",
                content="用户喜欢夜里写作。",
                importance=0.7,
                reason="semantic guard unavailable; queued for review",
            )
        )
        MemoryRepository(session).add(
            Memory(
                id="mem_rejected_candidate",
                user_id="user_001",
                character_id="char_001",
                scope="user_memory",
                status="candidate",
                content="临时玩笑应该写入长期记忆。",
                importance=0.4,
                reason="semantic guard queued this memory for review",
            )
        )
        session.commit()

    list_exit_code = main(
        [
            "list",
            "memories",
            "--user-id",
            "user_001",
            "--character-id",
            "char_001",
            "--status",
            "candidate",
        ]
    )
    list_output = capsys.readouterr().out

    review_exit_code = main(
        [
            "review",
            "memory",
            "mem_candidate",
            "--decision",
            "accept",
            "--reason",
            "用户明确确认这是稳定偏好。",
        ]
    )
    review_output = capsys.readouterr().out

    with session_factory() as session:
        reviewed = MemoryRepository(session).require("mem_candidate")

    assert list_exit_code == 0
    reject_exit_code = main(
        [
            "review",
            "memory",
            "mem_rejected_candidate",
            "--decision",
            "reject",
            "--reason",
            "这是临时玩笑，不应保存为长期记忆。",
        ]
    )
    reject_output = capsys.readouterr().out

    assert "memory_count=2" in list_output
    assert "memory.1.status=candidate" in list_output
    assert review_exit_code == 0
    assert "memory_id=mem_candidate" in review_output
    assert "status=accepted" in review_output
    assert reject_exit_code == 0
    assert "memory_id=mem_rejected_candidate" in reject_output
    assert "status=rejected" in reject_output
    assert reviewed.status == "accepted"
    assert "Review decision accepted" in reviewed.reason

    with session_factory() as session:
        rejected = MemoryRepository(session).require("mem_rejected_candidate")

    assert rejected.status == "rejected"
    assert "Review decision rejected" in rejected.reason


def test_cli_review_rejects_non_candidate_memory(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    create_all(engine)
    with session_factory() as session:
        MemoryRepository(session).add(
            Memory(
                id="mem_accepted",
                user_id="user_001",
                character_id="char_001",
                scope="user_memory",
                status="accepted",
                content="用户喜欢夜里写作。",
                importance=0.7,
                reason="already accepted",
            )
        )
        session.commit()

    exit_code = main(
        [
            "review",
            "memory",
            "mem_accepted",
            "--decision",
            "reject",
            "--reason",
            "重新审核。",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "only candidate memories can be reviewed" in captured.err


def test_cli_summarizes_conversation(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    conversation_id = _output_value(demo_output, "conversation_id")

    summarize_exit_code = main(
        [
            "summarize",
            "conversation",
            conversation_id,
            "--messages",
            "2",
        ]
    )
    summarize_output = capsys.readouterr().out

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        conversation = ConversationRepository(session).require(conversation_id)

    assert demo_exit_code == 0
    assert summarize_exit_code == 0
    assert f"conversation_id={conversation_id}" in summarize_output
    assert "summary=stub provider:" in summarize_output
    assert conversation.summary.startswith("stub provider:")


def test_cli_shows_context_package_and_critic_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    context_package_id = _output_value(demo_output, "context_package_id")
    critic_report_id = _output_value(demo_output, "critic_report_id")

    show_context_exit_code = main(["show", "context-package", context_package_id])
    context_output = capsys.readouterr().out

    show_critic_exit_code = main(["show", "critic-report", critic_report_id])
    critic_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert show_context_exit_code == 0
    assert f"context_package_id={context_package_id}" in context_output
    assert "interaction_mode=reality_chat" in context_output
    assert "assembled_prompt<<END" in context_output
    assert "# Persona Core Self" in context_output
    assert show_critic_exit_code == 0
    assert f"critic_report_id={critic_report_id}" in critic_output
    assert "ooc_risk=low" in critic_output
    assert "suggested_action=accept" in critic_output
    assert "reasons<<END" in critic_output


def test_cli_shows_character_profile_and_lists_claims(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"
    monkeypatch.setenv("PJ_DATABASE_URL", database_url)

    demo_exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--alias",
            "阿霜",
            "--reuse-existing",
        ]
    )
    demo_output = capsys.readouterr().out
    character_id = _output_value(demo_output, "character_id")
    persona_version_id = _output_value(demo_output, "persona_version_id")

    show_exit_code = main(["show", "character", character_id])
    show_output = capsys.readouterr().out

    list_exit_code = main(
        [
            "list",
            "claims",
            "--character-id",
            character_id,
            "--status",
            "verified",
        ]
    )
    list_output = capsys.readouterr().out

    assert demo_exit_code == 0
    assert show_exit_code == 0
    assert f"character_id={character_id}" in show_output
    assert "canonical_name=林霜" in show_output
    assert "aliases=阿霜" in show_output
    assert f"latest_persona_version_id={persona_version_id}" in show_output
    assert "claim_status.verified=1" in show_output
    assert "claim_type.personality=1" in show_output
    assert "evidence_count=1" in show_output
    assert "core_self<<END" in show_output
    assert list_exit_code == 0
    assert f"character_id={character_id}" in list_output
    assert "claim_count=1" in list_output
    assert "claim.1.status=verified" in list_output
    assert "claim.1.type=personality" in list_output
    assert "claim.1.evidence_count=1" in list_output


def test_cli_show_conversation_reports_missing_conversation(tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'pjelly.db'}"

    exit_code = main(
        [
            "show",
            "conversation",
            "conv_missing",
            "--database-url",
            database_url,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "conv_missing" in captured.err


def _output_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"{key!r} was not found in output:\n{output}")

