from personality_jelly.domain import ContextPackage, Message, PersonaVersion


CRITIC_SYSTEM_PROMPT = """You evaluate a character roleplay response.

Check:
- OOC risk: personality, tone, values, and role consistency.
- Fact risk: contradiction with verified canon in the context.
- Memory risk: misuse of user or relationship memories.
- Mode risk: incorrect handling of reality chat, roleplay scene, co-creation, or meta discussion.

Return a concise structured report. Do not rewrite canon and do not generate the roleplay reply.
"""


def build_critic_user_prompt(
    *,
    persona: PersonaVersion,
    context_package: ContextPackage,
    user_message: Message | None,
    assistant_message: Message,
) -> str:
    return "\n".join(
        [
            f"persona_version_id: {persona.id}",
            f"persona_core_self: {persona.core_self}",
            f"interaction_mode: {context_package.interaction_mode}",
            "",
            "assembled_context:",
            context_package.assembled_prompt,
            "",
            "user_message:",
            user_message.content if user_message is not None else "unknown",
            "",
            "assistant_message:",
            assistant_message.content,
        ]
    )

