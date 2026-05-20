from __future__ import annotations

from personality_jelly.domain import InteractionMode


ROLEPLAY_MARKERS = (
    "进入",
    "场景",
    "原作场景",
    "剧情",
    "扮演",
    "你会怎么行动",
    "设定我们在",
    "假设我们现在",
)

CO_CREATION_MARKERS = (
    "共同创作",
    "一起创作",
    "一起写",
    "共创",
    "新剧情",
    "续写",
    "改写一段",
    "设计一个情节",
)

META_MARKERS = (
    "作者",
    "设定",
    "人设",
    "系统",
    "提示词",
    "prompt",
    "ai",
    "模型",
    "ooc",
)


def infer_interaction_mode(user_message: str) -> InteractionMode:
    normalized = user_message.strip().lower()
    if not normalized:
        return InteractionMode.REALITY_CHAT
    if _contains_any(normalized, CO_CREATION_MARKERS):
        return InteractionMode.CO_CREATION
    if _contains_any(normalized, ROLEPLAY_MARKERS):
        return InteractionMode.ROLEPLAY_SCENE
    if _contains_any(normalized, META_MARKERS):
        return InteractionMode.META_DISCUSSION
    return InteractionMode.REALITY_CHAT


def resolve_interaction_mode(
    user_message: str,
    *,
    explicit_mode: InteractionMode | None,
    current_mode: InteractionMode,
) -> InteractionMode:
    return explicit_mode or infer_interaction_mode(user_message) or current_mode


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)
