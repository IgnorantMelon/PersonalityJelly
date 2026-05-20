from personality_jelly.domain import InteractionMode
from personality_jelly.runtime import infer_interaction_mode, resolve_interaction_mode


def test_infer_interaction_mode_defaults_to_reality_chat() -> None:
    assert infer_interaction_mode("我今天工作很累。") == InteractionMode.REALITY_CHAT


def test_infer_interaction_mode_detects_roleplay_scene() -> None:
    assert (
        infer_interaction_mode("假设我们现在进入你的原作场景，你会怎么行动？")
        == InteractionMode.ROLEPLAY_SCENE
    )


def test_infer_interaction_mode_detects_co_creation() -> None:
    assert infer_interaction_mode("我们一起创作一段新剧情。") == InteractionMode.CO_CREATION


def test_infer_interaction_mode_detects_meta_discussion() -> None:
    assert infer_interaction_mode("你的角色设定和提示词是什么？") == InteractionMode.META_DISCUSSION


def test_resolve_interaction_mode_prefers_explicit_override() -> None:
    assert (
        resolve_interaction_mode(
            "我们一起创作一段新剧情。",
            explicit_mode=InteractionMode.REALITY_CHAT,
            current_mode=InteractionMode.ROLEPLAY_SCENE,
        )
        == InteractionMode.REALITY_CHAT
    )
