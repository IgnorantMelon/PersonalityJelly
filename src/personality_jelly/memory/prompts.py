from personality_jelly.domain import ContextPackage, CriticReport, Message


CURATOR_SYSTEM_PROMPT = """You curate long-term memories for a character conversation.

Rules:
- Save only stable, useful user facts, preferences, relationship commitments, or durable shared events.
- Do not save temporary jokes, one-off chatter, or unsupported sensitive assumptions.
- Never write or alter original canon facts.
- Use accepted for memories that should be active, rejected for unsafe/unhelpful candidates, and candidate for items needing review.
"""


def build_curator_user_prompt(
    *,
    context_package: ContextPackage,
    summary_short_term_scene_state: str,
    user_message: Message,
    assistant_message: Message,
    critic_report: CriticReport | None,
) -> str:
    critic_text = (
        "\n".join(
            [
                f"ooc_risk: {critic_report.ooc_risk}",
                f"fact_risk: {critic_report.fact_risk}",
                f"memory_risk: {critic_report.memory_risk}",
                f"mode_risk: {critic_report.mode_risk}",
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
            f"conversation_id: {context_package.conversation_id}",
            f"interaction_mode: {context_package.interaction_mode}",
            "",
            "context_summary:",
            _format_curator_context(
                context_package,
                summary_short_term_scene_state=summary_short_term_scene_state,
            ),
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


def _format_curator_context(
    context_package: ContextPackage,
    *,
    summary_short_term_scene_state: str,
) -> str:
    return "\n".join(
        [
            _without_conversation_summary(context_package.assembled_prompt),
            "",
            "# Conversation Summary For Memory Curation",
            "## short_term_scene_state",
            summary_short_term_scene_state or "none",
            "",
            "## excluded_summary_layers",
            "- user_memory_candidates: omitted; not verified accepted memories.",
            "- relationship_memory_notes: omitted; not accepted relationship memories and cannot "
            "rewrite canon or persona.",
            "- reflective_notes: omitted; not source evidence, canon claims, or persona fields.",
        ]
    )


def _without_conversation_summary(prompt: str) -> str:
    lines: list[str] = []
    skipping = False
    for line in prompt.splitlines():
        if line == "# Conversation Summary":
            skipping = True
            continue
        if skipping and line.startswith("# "):
            skipping = False
        if not skipping:
            lines.append(line)
    return "\n".join(lines).strip()

