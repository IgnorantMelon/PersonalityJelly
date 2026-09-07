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
    OpenAIJSONResponseFormat,
    OpenAICompatibleProvider,
    build_embedding_provider,
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


def _settings_without_project_file(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


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


def test_generate_json_can_request_json_object_and_inject_schema_instruction() -> None:
    transport = FakeTransport(
        {"choices": [{"message": {"content": '{"answer": "ok"}'}}]},
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            api_key="secret",
            json_response_format=OpenAIJSONResponseFormat.JSON_OBJECT,
        ),
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
    payload = transport.calls[0]["payload"]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0]["role"] == "system"
    assert "Return only one JSON object" in payload["messages"][0]["content"]
    assert '"title": "Answer"' in payload["messages"][0]["content"]
    assert payload["messages"][1] == {"role": "user", "content": "return json"}


def test_generate_json_json_object_appends_instruction_to_existing_system_message() -> None:
    transport = FakeTransport(
        {"choices": [{"message": {"content": '{"answer": "ok"}'}}]},
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            api_key="secret",
            json_response_format=OpenAIJSONResponseFormat.JSON_OBJECT,
        ),
        transport=transport,
    )

    provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content="existing system"),
            ChatMessage(role=MessageRole.USER, content="return json"),
        ],
        schema={"title": "Answer", "type": "object"},
        model_config=ModelConfig(model="chat-model"),
    )

    payload_messages = transport.calls[0]["payload"]["messages"]
    assert len(payload_messages) == 2
    assert payload_messages[0]["role"] == "system"
    assert payload_messages[0]["content"].startswith("existing system\n\n")
    assert "Return only one JSON object" in payload_messages[0]["content"]
    assert payload_messages[1] == {"role": "user", "content": "return json"}


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
    settings = _settings_without_project_file()

    provider = build_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.base_url == "https://llm.example/v1"
    assert provider.config.api_key == "secret"
    assert provider.config.timeout_seconds == 7
    assert provider.config.json_response_format == OpenAIJSONResponseFormat.JSON_SCHEMA


def test_build_llm_provider_can_use_json_object_response_format(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("PJ_LLM_API_KEY", "secret")
    monkeypatch.setenv("PJ_LLM_JSON_RESPONSE_FORMAT", "json_object")

    provider = build_llm_provider(_settings_without_project_file())

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.json_response_format == OpenAIJSONResponseFormat.JSON_OBJECT


def test_build_llm_provider_rejects_unknown_json_response_format(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "secret")
    monkeypatch.setenv("PJ_LLM_JSON_RESPONSE_FORMAT", "xml")

    with pytest.raises(ValueError, match="PJ_LLM_JSON_RESPONSE_FORMAT"):
        build_llm_provider(_settings_without_project_file())


def test_build_embedding_provider_can_use_separate_cloud_settings(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("PJ_LLM_API_KEY", "chat-secret")
    monkeypatch.setenv("PJ_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_EMBEDDING_BASE_URL", "https://embedding.example/v1")
    monkeypatch.setenv("PJ_EMBEDDING_API_KEY", "embedding-secret")
    monkeypatch.setenv("PJ_EMBEDDING_TIMEOUT_SECONDS", "9")

    provider = build_embedding_provider(_settings_without_project_file())

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.base_url == "https://embedding.example/v1"
    assert provider.config.api_key == "embedding-secret"
    assert provider.config.timeout_seconds == 9


def test_build_embedding_provider_defaults_to_llm_cloud_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("PJ_LLM_API_KEY", "chat-secret")
    monkeypatch.delenv("PJ_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("PJ_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("PJ_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("PJ_CONFIG_FILE", raising=False)

    provider = build_embedding_provider(_settings_without_project_file())

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.base_url == "https://chat.example/v1"
    assert provider.config.api_key == "chat-secret"


def test_build_embedding_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("PJ_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "")
    monkeypatch.setenv("PJ_EMBEDDING_API_KEY", "")
    monkeypatch.delenv("PJ_CONFIG_FILE", raising=False)

    with pytest.raises(ValueError, match="PJ_EMBEDDING_API_KEY"):
        build_embedding_provider(_settings_without_project_file())


def test_build_llm_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("PJ_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PJ_LLM_API_KEY", "")
    monkeypatch.delenv("PJ_CONFIG_FILE", raising=False)

    with pytest.raises(ValueError, match="PJ_LLM_API_KEY"):
        build_llm_provider(_settings_without_project_file())
