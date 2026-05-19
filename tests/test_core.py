from personality_jelly.core import EntityKind, Settings, generate_id


def test_generate_id_uses_expected_prefix() -> None:
    generated = generate_id(EntityKind.CONVERSATION)

    assert generated.startswith("conv_")
    assert len(generated) > len("conv_")


def test_settings_use_project_env_prefix(monkeypatch) -> None:
    monkeypatch.setenv("PJ_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("PJ_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.database_url == "sqlite:///test.db"
    assert settings.log_level == "DEBUG"

