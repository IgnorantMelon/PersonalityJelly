from pathlib import Path

from personality_jelly.cli.main import main
from personality_jelly.llm import ChatMessage, ModelConfig
from personality_jelly.storage import (
    MessageRepository,
    create_database_engine,
    create_session_factory,
)
from personality_jelly.testing.stub_provider import StubProvider


class RecordingProvider(StubProvider):
    def __init__(self) -> None:
        self.model_names: list[str] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        self.model_names.append(model_config.model)
        return super().generate_text(messages, model_config)

    def generate_json(self, messages, schema, model_config):
        self.model_names.append(model_config.model)
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
    assert "assistant=我记住了" in output
    assert "critic_action=accept" in output
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


def test_cli_demo_env_provider_requires_model(tmp_path: Path, capsys, monkeypatch) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "test-key")
    monkeypatch.delenv("PJ_LLM_MODEL", raising=False)

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
    assert "assistant=我记住了" in turn_output
    assert [message.role for message in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[-2].content == "我们继续聊。"


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


def _output_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"{key!r} was not found in output:\n{output}")

