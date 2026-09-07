from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from personality_jelly.domain import Conversation, MessageRole
from personality_jelly.domain.models import utc_now
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder, record_structured_output
from personality_jelly.runtime.summary_prompts import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)
from personality_jelly.runtime.summary_schemas import ConversationSummaryDraft
from personality_jelly.storage import (
    ConversationRepository,
    LLMRawOutputRepository,
    MessageRepository,
)


CONVERSATION_SUMMARY_OPERATION = "runtime.summary.conversation_summary"


@dataclass(frozen=True)
class ConversationSummaryResult:
    conversation: Conversation


@dataclass(frozen=True)
class ConversationSummaryLayers:
    short_term_scene_state: str
    user_memory_candidates: list[str]
    relationship_memory_notes: list[str]
    reflective_notes: list[str]


def summarize_conversation(
    session: Session,
    *,
    conversation_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    max_messages: int = 20,
) -> ConversationSummaryResult:
    if max_messages < 1:
        raise ValueError("max_messages must be greater than 0")

    conversation_repository = ConversationRepository(session)
    conversation = conversation_repository.require(conversation_id)
    messages = MessageRepository(session).list_by_conversation(conversation.id)
    recent_messages = messages[-max_messages:]
    if not recent_messages:
        raise ValueError(f"Conversation {conversation_id!r} has no messages to summarize")

    schema = ConversationSummaryDraft.model_json_schema()
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=SUMMARY_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=build_summary_user_prompt(
                    conversation=conversation,
                    messages=recent_messages,
                ),
            ),
        ],
        schema=schema,
        model_config=model_config,
    )
    trace_recorder = RepositoryLLMTraceRecorder(LLMRawOutputRepository(session))
    try:
        draft = TypeAdapter(ConversationSummaryDraft).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=CONVERSATION_SUMMARY_OPERATION,
            schema_name=ConversationSummaryDraft.__name__,
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=CONVERSATION_SUMMARY_OPERATION,
        schema_name=ConversationSummaryDraft.__name__,
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=draft,
    )
    updated = conversation_repository.update_summary(
        conversation.id,
        summary=_format_layered_summary(draft),
        updated_at=utc_now(),
    )
    return ConversationSummaryResult(conversation=updated)


def parse_layered_summary(summary: str | None) -> ConversationSummaryLayers:
    if summary is None or not summary.strip():
        return ConversationSummaryLayers(
            short_term_scene_state="none",
            user_memory_candidates=[],
            relationship_memory_notes=[],
            reflective_notes=[],
        )

    sections = _parse_markdown_sections(summary)
    if not sections:
        return ConversationSummaryLayers(
            short_term_scene_state=summary.strip(),
            user_memory_candidates=[],
            relationship_memory_notes=[],
            reflective_notes=[],
        )

    return ConversationSummaryLayers(
        short_term_scene_state=_section_text(
            sections,
            "Short-term Scene State",
            default="none",
        ),
        user_memory_candidates=_section_items(sections, "User Memory Candidates"),
        relationship_memory_notes=_section_items(sections, "Relationship Memory Notes"),
        reflective_notes=_section_items(sections, "Reflective Notes"),
    )


def _format_layered_summary(draft: ConversationSummaryDraft) -> str:
    return "\n".join(
        [
            "# Short-term Scene State",
            draft.short_term_scene_state,
            "",
            "# User Memory Candidates",
            _format_items(draft.user_memory_candidates),
            "",
            "# Relationship Memory Notes",
            _format_items(draft.relationship_memory_notes),
            "",
            "# Reflective Notes",
            _format_items(draft.reflective_notes),
        ]
    )


def _format_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def _parse_markdown_sections(summary: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in summary.splitlines():
        if line.startswith("# "):
            current_heading = line[2:].strip()
            sections[current_heading] = []
            continue
        if current_heading is not None:
            sections[current_heading].append(line)
    return sections


def _section_text(
    sections: dict[str, list[str]],
    heading: str,
    *,
    default: str,
) -> str:
    text = "\n".join(line for line in sections.get(heading, [])).strip()
    return text if text else default


def _section_items(sections: dict[str, list[str]], heading: str) -> list[str]:
    items: list[str] = []
    for line in sections.get(heading, []):
        stripped = line.strip()
        if not stripped or stripped == "- none":
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        else:
            items.append(stripped)
    return items
