from pathlib import Path

from personality_jelly.cli.main import main
from personality_jelly.llm import ChatMessage, ModelConfig
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

