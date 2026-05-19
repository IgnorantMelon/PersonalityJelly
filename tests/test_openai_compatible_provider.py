from __future__ import annotations

import pytest

from personality_jelly.core import Settings
from personality_jelly.domain import MessageRole
from personality_jelly.llm import (
    ChatMessage,
    EmbeddingConfig,
    ModelConfig,
    OpenAICompatibleConfig,
    OpenAICompatibleError,
    OpenAICompatibleProvider,
    build_llm_provider,
)


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def test_generate_text_posts_chat_completion_payload() -> None:
    transport = FakeTransport(
        {"choices": [{"message": {"content": "hello"}}]},
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="https://llm.example/v1/",
            api_key="secret",
            timeout_seconds=12,
        ),
        transport=transport,
    )

    result = provider.generate_text(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content="system"),
            ChatMessage(role=MessageRole.USER, content="user"),
        ],
        model_config=ModelConfig(model="chat-model", temperature=0.4, max_tokens=128),
    )

    assert result == "hello"
    assert transport.calls[0]["url"] == "https://llm.example/v1/chat/completions"
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer secret"
    assert transport.calls[0]["timeout"] == 12
    assert transport.calls[0]["payload"] == {
        "model": "chat-model",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        "temperature": 0.4,
        "max_tokens": 128,
    }


def test_generate_json_requests_json_schema_and_decodes_content() -> None:
    transport = FakeTransport(
        {"choices": [{"message": {"content": '{"answer": "ok"}'}}]},
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(api_key="secret"),
        transport=transport,
    )
    schema = {
        "title": "Answer",
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    result = provider.generate_json(
        messages=[ChatMessage(role=MessageRole.USER, content="return json")],
        schema=schema,
        model_config=ModelConfig(model="chat-model"),
    )

    assert result == {"answer": "ok"}
    response_format = transport.calls[0]["payload"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"] == {
        "name": "Answer",
        "schema": schema,
        "strict": True,
    }


def test_generate_json_rejects_non_object_content() -> None:
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(api_key="secret"),
        transport=FakeTransport({"choices": [{"message": {"content": "[1, 2]"}}]}),
    )

    with pytest.raises(OpenAICompatibleError, match="not an object"):
        provider.generate_json(
            messages=[ChatMessage(role=MessageRole.USER, content="return json")],
            schema={"title": "Answer", "type": "object"},
            model_config=ModelConfig(model="chat-model"),
        )


def test_embed_texts_posts_embeddings_payload_and_sorts_by_index() -> None:
    transport = FakeTransport(
        {
            "data": [
                {"index": 1, "embedding": [0, 2]},
                {"index": 0, "embedding": [1.5, 3]},
            ]
        },
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="https://llm.example/v1",
            api_key="secret",
        ),
        transport=transport,
    )

    embeddings = provider.embed_texts(
        ["first", "second"],
        EmbeddingConfig(model="embedding-model"),
    )

    assert embeddings == [[1.5, 3.0], [0.0, 2.0]]
    assert transport.calls[0]["url"] == "https://llm.example/v1/embeddings"
    assert transport.calls[0]["payload"] == {
        "model": "embedding-model",
        "input": ["first", "second"],
    }


def test_embed_texts_short_circuits_empty_input() -> None:
    transport = FakeTransport({"data": []})
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(api_key="secret"),
        transport=transport,
    )

    assert provider.embed_texts([], EmbeddingConfig(model="embedding-model")) == []
    assert transport.calls == []


def test_build_llm_provider_from_settings(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("PJ_LLM_API_KEY", "secret")
    monkeypatch.setenv("PJ_LLM_TIMEOUT_SECONDS", "7")
    settings = Settings()

    provider = build_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.base_url == "https://llm.example/v1"
    assert provider.config.api_key == "secret"
    assert provider.config.timeout_seconds == 7


def test_build_llm_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("PJ_LLM_API_KEY", raising=False)

    with pytest.raises(ValueError, match="PJ_LLM_API_KEY"):
        build_llm_provider(Settings())
