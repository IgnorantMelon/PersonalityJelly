from personality_jelly.domain import CanonClaim, Character


COMPILER_SYSTEM_PROMPT = """You compile verified canon claims into a runnable character persona.

Rules:
- Use only verified claims supplied by the user message.
- Keep core self separate from reality interaction rules.
- Include explicit canon-protection forbidden rules.
- Do not include conflicted, rejected, or unsupported facts.
- Produce concise, operational rules suitable for a roleplay agent.
"""


def build_compiler_user_prompt(
    *,
    character: Character,
    claims: list[CanonClaim],
) -> str:
    claim_lines = "\n".join(
        f"- claim_id: {claim.id}\n  type: {claim.claim_type}\n  content: {claim.content}"
        for claim in claims
    )
    return (
        f"Character: {character.canonical_name}\n"
        f"Aliases: {', '.join(character.aliases) if character.aliases else 'none'}\n\n"
        "Verified claims:\n"
        f"{claim_lines}\n\n"
        "Compile these into persona fields."
    )

