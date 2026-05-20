from __future__ import annotations

from personality_jelly.domain import Conversation, Message


SUMMARY_SYSTEM_PROMPT = """Summarize a character conversation for future context.

Keep canon and user memory separate. Do not turn temporary roleplay or jokes into original canon.
Focus on durable conversation state, user preferences, relationship changes, unresolved topics,
and mode-relevant context. Return a concise structured summary.
"""


def build_summary_user_prompt(
    *,
    conversation: Conversation,
    messages: list[Message],
) -> str:
    lines = [
        f"conversation_id: {conversation.id}",
        f"character_id: {conversation.character_id}",
        f"user_id: {conversation.user_id}",
        f"current_mode: {conversation.current_mode}",
        "",
        "previous_summary:",
        conversation.summary or "none",
        "",
        "recent_messages:",
    ]
    lines.extend(
        f"- {message.role}: {message.content}"
        for message in messages
    )
    return "\n".join(lines)
