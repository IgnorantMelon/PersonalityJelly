from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain.enums import MessageRole


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    role: MessageRole
    content: str


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str


class LLMProvider(Protocol):
    name: str

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        """Generate free-form text from chat messages."""

    def generate_json(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        model_config: ModelConfig,
    ) -> dict[str, Any]:
        """Generate JSON constrained by the supplied schema."""

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        """Embed a batch of texts."""

