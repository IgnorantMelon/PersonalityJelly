from __future__ import annotations

from personality_jelly.domain import Conversation, Message


SUMMARY_SYSTEM_PROMPT = """Summarize a character conversation for future context.

Return separate fields. Do not merge categories.

- short_term_scene_state: temporary scene, task state, unresolved topics, and mode-relevant context.
- user_memory_candidates: durable user preferences or facts only; these are still candidates for
  the separate memory workflow, not accepted memories.
- relationship_memory_notes: durable relationship changes between user and character only.
- reflective_notes: operational lessons about boundaries or risks only.

Do not put original canon, persona core, temporary roleplay, jokes, or co-created fiction into user
memory candidates or relationship memory notes. Do not let user conversation rewrite canon.
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
        "summary_boundaries:",
        "- Keep short-term scene state separate from durable user memory candidates.",
        "- Keep relationship memory separate from user preferences.",
        "- Keep reflective notes separate from canon and persona core.",
        "- Temporary roleplay, jokes, and co-created fiction are not canon.",
        "",
        "recent_messages:",
    ]
    lines.extend(
        f"- {message.role}: {message.content}"
        for message in messages
    )
    return "\n".join(lines)
