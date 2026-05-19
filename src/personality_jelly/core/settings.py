from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PJ_",
        extra="ignore",
    )

    database_url: str = "sqlite:///personality_jelly.db"
    default_language: str = "zh-CN"
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0.0)
    embedding_model: str | None = None
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

