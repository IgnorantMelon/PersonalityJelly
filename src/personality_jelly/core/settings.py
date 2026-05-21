from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PJ_",
        extra="ignore",
    )

    config_file: str = "pjelly.toml"
    database_url: str = "sqlite:///personality_jelly.db"
    default_language: str = "zh-CN"
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0.0)
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_timeout_seconds: float | None = Field(default=None, gt=0.0)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            ProjectTomlSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def resolved_config_file(self) -> Path:
        return Path(self.config_file)


class ProjectTomlSettingsSource(PydanticBaseSettingsSource):
    """Load non-secret project defaults from a flat or sectioned TOML file."""

    def get_field_value(self, field, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        path = _config_path(self.current_state)
        if not path.is_file():
            return {}
        data = _load_toml(path)
        return _flatten_project_config(data)


def _config_path(current_state: dict[str, Any]) -> Path:
    state_value = current_state.get("config_file")
    if isinstance(state_value, str) and state_value.strip():
        return Path(state_value.strip())
    configured = os.environ.get("PJ_CONFIG_FILE")
    if configured and configured.strip():
        return Path(configured.strip())
    return Path("pjelly.toml")


def _load_toml(path: Path) -> dict[str, Any]:
    import tomllib

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)
    if not isinstance(data, dict):
        return {}
    return data


def _flatten_project_config(data: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    _copy_scalar(data, flattened, "database_url")
    _copy_scalar(data, flattened, "default_language")
    _copy_scalar(data, flattened, "log_level")

    _copy_section(
        data.get("llm"),
        flattened,
        prefix="llm",
        fields=("provider", "model", "base_url", "timeout_seconds"),
    )
    _copy_section(
        data.get("embedding"),
        flattened,
        prefix="embedding",
        fields=("provider", "model", "base_url", "timeout_seconds"),
    )
    return flattened


def _copy_scalar(source: dict[str, Any], target: dict[str, Any], key: str) -> None:
    value = source.get(key)
    if _is_supported_scalar(value):
        target[key] = value


def _copy_section(
    section: Any,
    target: dict[str, Any],
    *,
    prefix: str,
    fields: tuple[str, ...],
) -> None:
    if not isinstance(section, dict):
        return
    for field_name in fields:
        value = section.get(field_name)
        if _is_supported_scalar(value):
            target[f"{prefix}_{field_name}"] = value


def _is_supported_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool)

