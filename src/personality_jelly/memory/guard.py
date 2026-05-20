from __future__ import annotations

from dataclasses import dataclass

from personality_jelly.domain import CriticReport, MemoryStatus, Message
from personality_jelly.memory.schemas import MemoryCandidate


@dataclass(frozen=True)
class GuardedMemoryCandidate:
    candidate: MemoryCandidate
    rejection_reasons: list[str]


CANON_POLLUTION_TERMS = (
    "canon",
    "original canon",
    "source canon",
    "原作",
    "正史",
    "设定",
    "真实过去",
    "真实经历",
    "核心人格",
)

UNSAFE_ACTION_TERMS = (
    "rewrite",
    "override",
    "replace",
    "alter",
    "change",
    "改写",
    "覆盖",
    "替换",
    "更改",
    "改变",
    "当成",
    "记为",
    "写入",
)

EPHEMERAL_TERMS = (
    "joke",
    "just kidding",
    "pretend",
    "temporary",
    "one-off",
    "玩笑",
    "开玩笑",
    "假装",
    "临时",
    "刚才",
    "随口",
)


def guard_memory_candidate(
    candidate: MemoryCandidate,
    *,
    user_message: Message,
    assistant_message: Message,
    critic_report: CriticReport | None,
) -> GuardedMemoryCandidate:
    reasons = _rejection_reasons(
        candidate,
        user_message=user_message,
        assistant_message=assistant_message,
        critic_report=critic_report,
    )
    if not reasons:
        return GuardedMemoryCandidate(candidate=candidate, rejection_reasons=[])

    return GuardedMemoryCandidate(
        candidate=candidate.model_copy(
            update={
                "status": MemoryStatus.REJECTED,
                "importance": min(candidate.importance, 0.2),
                "reason": _append_guard_reason(candidate.reason, reasons),
            }
        ),
        rejection_reasons=reasons,
    )


def guard_memory_candidates(
    candidates: list[MemoryCandidate],
    *,
    user_message: Message,
    assistant_message: Message,
    critic_report: CriticReport | None,
) -> list[GuardedMemoryCandidate]:
    return [
        guard_memory_candidate(
            candidate,
            user_message=user_message,
            assistant_message=assistant_message,
            critic_report=critic_report,
        )
        for candidate in candidates
    ]


def _rejection_reasons(
    candidate: MemoryCandidate,
    *,
    user_message: Message,
    assistant_message: Message,
    critic_report: CriticReport | None,
) -> list[str]:
    if candidate.status == MemoryStatus.REJECTED:
        return []

    context_text = " ".join(
        [
            candidate.content,
            candidate.reason,
            user_message.content,
            assistant_message.content,
            " ".join(critic_report.reasons if critic_report is not None else []),
        ]
    )
    normalized = context_text.casefold()
    reasons: list[str] = []

    if _contains_any(normalized, CANON_POLLUTION_TERMS) and _contains_any(
        normalized,
        UNSAFE_ACTION_TERMS,
    ):
        reasons.append("deterministic guard: possible canon rewrite or canon pollution")

    if _contains_any(normalized, EPHEMERAL_TERMS) and _contains_any(
        normalized,
        UNSAFE_ACTION_TERMS,
    ):
        reasons.append("deterministic guard: temporary joke or roleplay should not be saved")

    if critic_report is not None and critic_report.memory_risk == "high":
        reasons.append("deterministic guard: critic reported high memory risk")

    return reasons


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.casefold() in text for term in terms)


def _append_guard_reason(reason: str, rejection_reasons: list[str]) -> str:
    return f"{reason} Guard rejected: {'; '.join(rejection_reasons)}"
