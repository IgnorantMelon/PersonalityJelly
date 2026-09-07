from personality_jelly.core import EntityKind, Settings, generate_id


def _settings_without_project_file(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_generate_id_uses_expected_prefix() -> None:
    generated = generate_id(EntityKind.CONVERSATION)

    assert generated.startswith("conv_")
    assert len(generated) > len("conv_")


def test_settings_use_project_env_prefix(monkeypatch) -> None:
    monkeypatch.setenv("PJ_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("PJ_LOG_LEVEL", "DEBUG")

    settings = _settings_without_project_file()

    assert settings.database_url == "sqlite:///test.db"
    assert settings.log_level == "DEBUG"


def test_settings_load_non_secret_values_from_project_toml(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "pjelly.toml"
    config_file.write_text(
        """
database_url = "sqlite:///configured.db"
log_level = "WARNING"

[llm]
provider = "openai-compatible"
base_url = "https://chat.example/v1"
model = "chat-model"
timeout_seconds = 30
json_response_format = "json_object"

[embedding]
provider = "openai-compatible"
base_url = "https://embedding.example/v1"
model = "embedding-model"
timeout_seconds = 15
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PJ_CONFIG_FILE", str(config_file))

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///configured.db"
    assert settings.log_level == "WARNING"
    assert settings.llm_provider == "openai-compatible"
    assert settings.llm_base_url == "https://chat.example/v1"
    assert settings.llm_model == "chat-model"
    assert settings.llm_timeout_seconds == 30
    assert settings.llm_json_response_format == "json_object"
    assert settings.embedding_provider == "openai-compatible"
    assert settings.embedding_base_url == "https://embedding.example/v1"
    assert settings.embedding_model == "embedding-model"
    assert settings.embedding_timeout_seconds == 15


def test_environment_overrides_project_toml(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "pjelly.toml"
    config_file.write_text(
        """
[llm]
provider = "openai-compatible"
base_url = "https://configured.example/v1"
model = "configured-model"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PJ_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("PJ_LLM_MODEL", "env-model")

    settings = Settings(_env_file=None)

    assert settings.llm_base_url == "https://configured.example/v1"
    assert settings.llm_model == "env-model"


def test_project_toml_does_not_load_api_keys(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "pjelly.toml"
    config_file.write_text(
        """
[llm]
provider = "openai-compatible"
api_key = "unsafe-llm-key"

[embedding]
provider = "openai-compatible"
api_key = "unsafe-embedding-key"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PJ_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("PJ_LLM_API_KEY", "")
    monkeypatch.setenv("PJ_EMBEDDING_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.llm_api_key == ""
    assert settings.embedding_api_key == ""


def test_init_config_file_selects_project_toml(tmp_path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
        """
[llm]
provider = "openai-compatible"
model = "custom-model"
""".strip(),
        encoding="utf-8",
    )

    settings = Settings(config_file=str(config_file), _env_file=None)

    assert settings.resolved_config_file == config_file
    assert settings.llm_model == "custom-model"

