from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from personality_jelly.domain import CriticReport, InteractionMode, MemoryStatus, Message, MessageRole
from personality_jelly.llm import ChatMessage, LLMProvider, ModelConfig
from personality_jelly.llm.tracing import LLMTraceRecorder, record_structured_output
from personality_jelly.memory.schemas import MemoryCandidate


MEMORY_GUARD_OPERATION = "memory.guard.semantic_decision"
MEMORY_GUARD_SYSTEM_PROMPT = """Evaluate whether a proposed long-term memory should be saved.

Judge semantically. Do not use fixed trigger words or literal text matching. Consider:
- source_grounding: whether the memory is grounded in the user's statement or a durable shared event.
- stability: whether it is durable enough for long-term memory.
- scope_fit: whether the proposed memory belongs in the requested memory scope.
- canon_pollution_risk: whether it would rewrite or contaminate original canon/persona.
- roleplay_contamination_risk: whether temporary scenes, jokes, or co-created fiction are being stored as durable memory.

Return a structured decision. Use reject for unsafe or unsupported memories, candidate for uncertain
items needing review, and accept only for clearly grounded durable memories.
"""


@dataclass(frozen=True)
class GuardedMemoryCandidate:
    candidate: MemoryCandidate
    rejection_reasons: list[str]
    decision: str


class MemoryGuardDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(accept|candidate|reject)$")
    source_grounding: str
    stability: str
    scope_fit: str
    canon_pollution_risk: str
    roleplay_contamination_risk: str
    reasoning: str


def guard_memory_candidate(
    candidate: MemoryCandidate,
    *,
    user_message: Message,
    assistant_message: Message,
    interaction_mode: InteractionMode,
    critic_report: CriticReport | None,
    provider: LLMProvider | None,
    model_config: ModelConfig | None,
    trace_recorder: LLMTraceRecorder | None = None,
) -> GuardedMemoryCandidate:
    if candidate.status == MemoryStatus.REJECTED:
        return GuardedMemoryCandidate(
            candidate=candidate,
            rejection_reasons=[],
            decision="reject",
        )

    if critic_report is not None and critic_report.memory_risk == "high":
        return _apply_guard_decision(
            candidate,
            decision="reject",
            reason="deterministic policy: critic reported high memory risk",
        )

    if provider is None or model_config is None:
        updated = candidate.model_copy(
            update={
                "status": MemoryStatus.CANDIDATE,
                "reason": _append_guard_reason(
                    candidate.reason,
                    "semantic guard unavailable; queued for review",
                ),
            }
        )
        return GuardedMemoryCandidate(candidate=updated, rejection_reasons=[], decision="candidate")

    decision = _semantic_guard_decision(
        candidate,
        user_message=user_message,
        assistant_message=assistant_message,
        interaction_mode=interaction_mode,
        critic_report=critic_report,
        provider=provider,
        model_config=model_config,
        trace_recorder=trace_recorder,
    )
    if decision.decision == "accept":
        return GuardedMemoryCandidate(candidate=candidate, rejection_reasons=[], decision="accept")
    if decision.decision == "candidate":
        updated = candidate.model_copy(
            update={
                "status": MemoryStatus.CANDIDATE,
                "reason": _append_guard_reason(candidate.reason, decision.reasoning),
            }
        )
        return GuardedMemoryCandidate(
            candidate=updated,
            rejection_reasons=[],
            decision="candidate",
        )
    return _apply_guard_decision(candidate, decision="reject", reason=decision.reasoning)


def guard_memory_candidates(
    candidates: list[MemoryCandidate],
    *,
    user_message: Message,
    assistant_message: Message,
    interaction_mode: InteractionMode,
    critic_report: CriticReport | None,
    provider: LLMProvider | None,
    model_config: ModelConfig | None,
    trace_recorder: LLMTraceRecorder | None = None,
) -> list[GuardedMemoryCandidate]:
    return [
        guard_memory_candidate(
            candidate,
            user_message=user_message,
            assistant_message=assistant_message,
            interaction_mode=interaction_mode,
            critic_report=critic_report,
            provider=provider,
            model_config=model_config,
            trace_recorder=trace_recorder,
        )
        for candidate in candidates
    ]


def _semantic_guard_decision(
    candidate: MemoryCandidate,
    *,
    user_message: Message,
    assistant_message: Message,
    interaction_mode: InteractionMode,
    critic_report: CriticReport | None,
    provider: LLMProvider,
    model_config: ModelConfig,
    trace_recorder: LLMTraceRecorder | None = None,
) -> MemoryGuardDecision:
    schema = MemoryGuardDecision.model_json_schema()
    raw = provider.generate_json(
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content=MEMORY_GUARD_SYSTEM_PROMPT),
            ChatMessage(
                role=MessageRole.USER,
                content=_build_guard_prompt(
                    candidate,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    interaction_mode=interaction_mode,
                    critic_report=critic_report,
                ),
            ),
        ],
        schema=schema,
        model_config=model_config,
    )
    try:
        decision = TypeAdapter(MemoryGuardDecision).validate_python(raw)
    except ValidationError as exc:
        record_structured_output(
            recorder=trace_recorder,
            operation=MEMORY_GUARD_OPERATION,
            schema_name="MemoryGuardDecision",
            provider=provider,
            model_config=model_config,
            response_schema=schema,
            raw_output=raw,
            validation_error=exc,
        )
        raise
    record_structured_output(
        recorder=trace_recorder,
        operation=MEMORY_GUARD_OPERATION,
        schema_name="MemoryGuardDecision",
        provider=provider,
        model_config=model_config,
        response_schema=schema,
        raw_output=raw,
        parsed_output=decision,
    )
    return decision


def _build_guard_prompt(
    candidate: MemoryCandidate,
    *,
    user_message: Message,
    assistant_message: Message,
    interaction_mode: InteractionMode,
    critic_report: CriticReport | None,
) -> str:
    critic_text = (
        "\n".join(
            [
                f"memory_risk: {critic_report.memory_risk}",
                f"suggested_action: {critic_report.suggested_action}",
                "reasons:",
                *[f"- {reason}" for reason in critic_report.reasons],
            ]
        )
        if critic_report is not None
        else "none"
    )
    return "\n".join(
        [
            f"interaction_mode: {interaction_mode}",
            "",
            "candidate:",
            f"scope: {candidate.scope}",
            f"status: {candidate.status}",
            f"content: {candidate.content}",
            f"importance: {candidate.importance}",
            f"reason: {candidate.reason}",
            "",
            "user_message:",
            user_message.content,
            "",
            "assistant_message:",
            assistant_message.content,
            "",
            "critic_report:",
            critic_text,
        ]
    )


def _apply_guard_decision(
    candidate: MemoryCandidate,
    *,
    decision: str,
    reason: str,
) -> GuardedMemoryCandidate:
    updated = candidate.model_copy(
        update={
            "status": MemoryStatus.REJECTED,
            "importance": min(candidate.importance, 0.2),
            "reason": _append_guard_reason(candidate.reason, reason),
        }
    )
    return GuardedMemoryCandidate(
        candidate=updated,
        rejection_reasons=[reason],
        decision=decision,
    )


def _append_guard_reason(reason: str, guard_reason: str) -> str:
    return f"{reason} Guard decision: {guard_reason}"
