from personality_jelly.domain import InteractionMode
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.runtime import infer_interaction_mode, resolve_interaction_mode


class ModeClassifierFakeProvider:
    name = "mode-classifier-fake"

    def __init__(self, mode: InteractionMode) -> None:
        self.mode = mode

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "mode": self.mode,
            "confidence": 0.93,
            "reasoning": "fake provider supplied a structured mode decision.",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_infer_interaction_mode_uses_structured_classifier_result() -> None:
    assert (
        infer_interaction_mode(
            "用户消息内容不由本地文本触发逻辑解释。",
            provider=ModeClassifierFakeProvider(InteractionMode.ROLEPLAY_SCENE),
            model_config=ModelConfig(model="fake-mode"),
        )
        == InteractionMode.ROLEPLAY_SCENE
    )


def test_resolve_interaction_mode_keeps_current_mode_without_classifier() -> None:
    assert (
        resolve_interaction_mode(
            "没有模型分类器时不做本地语义猜测。",
            explicit_mode=None,
            current_mode=InteractionMode.CO_CREATION,
        )
        == InteractionMode.CO_CREATION
    )


def test_resolve_interaction_mode_prefers_explicit_override() -> None:
    assert (
        resolve_interaction_mode(
            "我们一起创作一段新剧情。",
            explicit_mode=InteractionMode.REALITY_CHAT,
            current_mode=InteractionMode.ROLEPLAY_SCENE,
        )
        == InteractionMode.REALITY_CHAT
    )
