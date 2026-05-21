from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain import MessageRole
from personality_jelly.llm.provider import ChatMessage, EmbeddingConfig, ModelConfig


class OpenAICompatibleError(RuntimeError):
    """Raised when an OpenAI-compatible endpoint returns an unusable response."""


class OpenAIJSONResponseFormat(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


class HTTPTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """POST JSON and return a decoded JSON object."""


@dataclass(frozen=True)
class UrllibHTTPTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        request = Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OpenAICompatibleError(
                f"OpenAI-compatible request failed with HTTP {exc.code}: {body}"
            ) from exc
        except URLError as exc:
            raise OpenAICompatibleError(f"OpenAI-compatible request failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenAICompatibleError("OpenAI-compatible endpoint returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise OpenAICompatibleError("OpenAI-compatible endpoint returned non-object JSON")
        return decoded


class OpenAICompatibleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(default="https://api.openai.com/v1")
    api_key: str
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    json_response_format: OpenAIJSONResponseFormat = OpenAIJSONResponseFormat.JSON_SCHEMA

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/embeddings"


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        response = self.transport.post_json(
            url=self.config.chat_completions_url,
            headers=self._headers(),
            payload=self._chat_payload(messages, model_config),
            timeout=self.config.timeout_seconds,
        )
        return _extract_message_content(response)

    def generate_json(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        model_config: ModelConfig,
    ) -> dict[str, Any]:
        payload = self._chat_payload(
            _structured_messages(
                messages,
                json_response_format=self.config.json_response_format,
                schema=schema,
            ),
            model_config,
        )
        payload["response_format"] = _structured_response_format(
            self.config.json_response_format,
            schema,
        )
        response = self.transport.post_json(
            url=self.config.chat_completions_url,
            headers=self._headers(),
            payload=payload,
            timeout=self.config.timeout_seconds,
        )
        content = _extract_message_content(response)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAICompatibleError(
                "OpenAI-compatible endpoint returned non-JSON message content"
            ) from exc
        if not isinstance(decoded, dict):
            raise OpenAICompatibleError("OpenAI-compatible JSON response content is not an object")
        return decoded

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        if not texts:
            return []
        response = self.transport.post_json(
            url=self.config.embeddings_url,
            headers=self._headers(),
            payload={
                "model": embedding_config.model,
                "input": texts,
            },
            timeout=self.config.timeout_seconds,
        )
        return _extract_embeddings(response)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_payload(
        self,
        messages: list[ChatMessage],
        model_config: ModelConfig,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_config.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            "temperature": model_config.temperature,
        }
        if model_config.max_tokens is not None:
            payload["max_tokens"] = model_config.max_tokens
        return payload


def _schema_name(schema: dict[str, Any]) -> str:
    title = schema.get("title")
    if isinstance(title, str) and title:
        return title
    return "StructuredResponse"


def _structured_messages(
    messages: list[ChatMessage],
    *,
    json_response_format: OpenAIJSONResponseFormat,
    schema: dict[str, Any],
) -> list[ChatMessage]:
    if json_response_format == OpenAIJSONResponseFormat.JSON_SCHEMA:
        return messages

    instruction = _json_object_schema_instruction(schema)
    if messages and messages[0].role == MessageRole.SYSTEM:
        return [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=f"{messages[0].content}\n\n{instruction}",
            ),
            *messages[1:],
        ]
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=instruction),
        *messages,
    ]


def _structured_response_format(
    json_response_format: OpenAIJSONResponseFormat,
    schema: dict[str, Any],
) -> dict[str, Any]:
    if json_response_format == OpenAIJSONResponseFormat.JSON_OBJECT:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _schema_name(schema),
            "schema": schema,
            "strict": True,
        },
    }


def _json_object_schema_instruction(schema: dict[str, Any]) -> str:
    encoded_schema = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    return (
        "Return only one JSON object that validates against this JSON Schema. "
        "Do not include Markdown, code fences, commentary, or any text outside the JSON object.\n"
        f"JSON Schema:\n{encoded_schema}"
    )


def _extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAICompatibleError("OpenAI-compatible response is missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenAICompatibleError("OpenAI-compatible response choice is not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenAICompatibleError("OpenAI-compatible response choice is missing message")
    content = message.get("content")
    if not isinstance(content, str):
        raise OpenAICompatibleError("OpenAI-compatible response message content is not text")
    return content


def _extract_embeddings(response: dict[str, Any]) -> list[list[float]]:
    data = response.get("data")
    if not isinstance(data, list):
        raise OpenAICompatibleError("OpenAI-compatible embeddings response is missing data")

    embeddings: list[list[float]] = []
    for item in sorted(data, key=_embedding_index):
        if not isinstance(item, dict):
            raise OpenAICompatibleError("OpenAI-compatible embedding item is not an object")
        embedding = item.get("embedding")
        if not isinstance(embedding, list) or not all(
            isinstance(value, int | float) for value in embedding
        ):
            raise OpenAICompatibleError("OpenAI-compatible embedding item is invalid")
        embeddings.append([float(value) for value in embedding])
    return embeddings


def _embedding_index(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    index = item.get("index")
    if isinstance(index, int):
        return index
    return 0
