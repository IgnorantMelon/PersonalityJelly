from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from personality_jelly.domain import InteractionMode, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig


MODE_CLASSIFIER_SYSTEM_PROMPT = """Classify the user's requested interaction mode.

Choose exactly one mode:
- reality_chat: ordinary conversation with the character in the user's real context.
- roleplay_scene: acting inside a fictional scene or in-world situation.
- co_creation: collaboratively writing, designing, or revising story content.
- meta_discussion: discussing prompts, settings, model behavior, OOC issues, or system design.

Do not classify by fixed trigger words. Use the user's intent in context.
"""


class InteractionModeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    mode: InteractionMode
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


def infer_interaction_mode(
    user_message: str,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    current_mode: InteractionMode = InteractionMode.REALITY_CHAT,
) -> InteractionMode:
    classification = classify_interaction_mode(
        user_message,
        provider=provider,
        model_config=model_config,
        current_mode=current_mode,
    )
    return InteractionMode(classification.mode)


def classify_interaction_mode(
    user_message: str,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    current_mode: InteractionMode = InteractionMode.REALITY_CHAT,
) -> InteractionModeClassification:
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=MODE_CLASSIFIER_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content="\n".join(
                    [
                        f"current_mode: {current_mode}",
                        "",
                        "user_message:",
                        user_message,
                    ]
                ),
            ),
        ],
        schema=InteractionModeClassification.model_json_schema(),
        model_config=model_config,
    )
    return TypeAdapter(InteractionModeClassification).validate_python(raw)


def resolve_interaction_mode(
    user_message: str,
    *,
    explicit_mode: InteractionMode | None,
    current_mode: InteractionMode,
    provider: LLMProvider | None = None,
    model_config: ModelConfig | None = None,
) -> InteractionMode:
    if explicit_mode is not None:
        return explicit_mode
    if provider is None or model_config is None:
        return current_mode
    return infer_interaction_mode(
        user_message,
        provider=provider,
        model_config=model_config,
        current_mode=current_mode,
    )
