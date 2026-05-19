READER_SYSTEM_PROMPT = """You extract structured canon claims about a target novel character.

Rules:
- Only extract claims supported by the supplied chunks.
- Every high-priority claim must include at least one evidence reference.
- Separate direct narration from other characters' opinions.
- Mark uncertain claims with lower confidence.
- Do not invent facts that are not in the chunks.
"""


def build_reader_user_prompt(
    *,
    canonical_name: str,
    aliases: list[str],
    chunks: list[tuple[str, str]],
) -> str:
    alias_text = ", ".join(aliases) if aliases else "none"
    chunk_text = "\n\n".join(f"[{chunk_id}]\n{text}" for chunk_id, text in chunks)
    return (
        f"Target character: {canonical_name}\n"
        f"Aliases: {alias_text}\n\n"
        "Extract candidate canon claims from these chunks:\n\n"
        f"{chunk_text}"
    )

