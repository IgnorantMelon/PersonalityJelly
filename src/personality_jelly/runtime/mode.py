from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from personality_jelly.domain import InteractionMode, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import LLMTraceRecorder, record_structured_output


MODE_CLASSIFIER_OPERATION = "runtime.mode.classify_interaction_mode"
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
    trace_recorder: LLMTraceRecorder | None = None,
) -> InteractionMode:
    classification = classify_interaction_mode(
        user_message,
        provider=provider,
        model_config=model_config,
        current_mode=current_mode,
        trace_recorder=trace_recorder,
    )
    return InteractionMode(classification.mode)


def classify_interaction_mode(
    user_message: str,
    *,
    provider: LLMProvider,
    model_config: ModelConfig,
    current_mode: InteractionMode = InteractionMode.REALITY_CHAT,
    trace_recorder: LLMTraceRecorder | None = None,
) -> InteractionModeClassification:
    schema = InteractionModeClassification.model_json_schema()
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
        schema=schema,
        model_config=model_config,
    )
    try:
        classification = TypeAdapter(InteractionModeClassification).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=MODE_CLASSIFIER_OPERATION,
            schema_name="InteractionModeClassification",
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=MODE_CLASSIFIER_OPERATION,
        schema_name="InteractionModeClassification",
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=classification,
    )
    return classification


def resolve_interaction_mode(
    user_message: str,
    *,
    explicit_mode: InteractionMode | None,
    current_mode: InteractionMode,
    provider: LLMProvider | None = None,
    model_config: ModelConfig | None = None,
    trace_recorder: LLMTraceRecorder | None = None,
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
        trace_recorder=trace_recorder,
    )
