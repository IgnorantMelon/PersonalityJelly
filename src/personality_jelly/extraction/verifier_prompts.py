from personality_jelly.domain import CanonClaim, Character, EvidenceRef, SourceChunk


VERIFIER_SYSTEM_PROMPT = """You verify candidate canon claims against source evidence.

Rules:
- Only mark a claim verified when the evidence supports it.
- Mark unsupported or speculative claims rejected.
- Mark mutually incompatible claims conflicted and describe the conflict.
- Do not add new canon facts.
- Return one decision for every input claim.
"""


def build_verifier_user_prompt(
    *,
    character: Character,
    claims: list[CanonClaim],
    evidence_by_claim: dict[str, list[EvidenceRef]],
    chunks_by_id: dict[str, SourceChunk],
) -> str:
    claim_blocks = []
    for claim in claims:
        evidence_lines = []
        for evidence in evidence_by_claim.get(claim.id, []):
            chunk = chunks_by_id[evidence.chunk_id]
            evidence_lines.append(
                "\n".join(
                    [
                        f"- evidence_id: {evidence.id}",
                        f"  chunk_id: {evidence.chunk_id}",
                        f"  excerpt: {evidence.excerpt}",
                        f"  source_text: {chunk.text}",
                        f"  support_score: {evidence.support_score}",
                    ]
                )
            )
        evidence_text = "\n".join(evidence_lines) if evidence_lines else "- none"
        claim_blocks.append(
            "\n".join(
                [
                    f"claim_id: {claim.id}",
                    f"type: {claim.claim_type}",
                    f"content: {claim.content}",
                    f"reader_confidence: {claim.confidence}",
                    "evidence:",
                    evidence_text,
                ]
            )
        )

    return (
        f"Character: {character.canonical_name}\n"
        f"Aliases: {', '.join(character.aliases) if character.aliases else 'none'}\n\n"
        "Verify these candidate claims:\n\n"
        + "\n\n---\n\n".join(claim_blocks)
    )

