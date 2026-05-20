from __future__ import annotations

from dataclasses import dataclass
import math

from sqlalchemy.orm import Session

from personality_jelly.domain import Character, SourceChunk
from personality_jelly.llm import EmbeddingConfig, LLMProvider
from personality_jelly.storage import SourceChunkRepository


@dataclass(frozen=True)
class SourceRetrievalResult:
    chunks: list[SourceChunk]


def retrieve_source_chunks(
    session: Session,
    *,
    source_work_id: str,
    character: Character,
    query: str,
    limit: int = 4,
    provider: LLMProvider | None = None,
    embedding_config: EmbeddingConfig | None = None,
) -> SourceRetrievalResult:
    if limit < 1:
        raise ValueError("limit must be greater than 0")

    chunks = SourceChunkRepository(session).list_by_source_work(source_work_id)
    if not chunks:
        return SourceRetrievalResult(chunks=[])

    if provider is None or embedding_config is None:
        return SourceRetrievalResult(
            chunks=_character_anchor_chunks(chunks, character=character, limit=limit),
        )

    query_text = _retrieval_query_text(query=query, character=character)
    embeddings = provider.embed_texts(
        [query_text, *[chunk.text for chunk in chunks]],
        embedding_config=embedding_config,
    )
    query_embedding = embeddings[0]
    chunk_embeddings = embeddings[1:]
    scored = [
        (_cosine_similarity(query_embedding, chunk_embedding), index, chunk)
        for index, (chunk, chunk_embedding) in enumerate(zip(chunks, chunk_embeddings, strict=True))
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return SourceRetrievalResult(
        chunks=[chunk for score, _, chunk in scored[:limit] if score > 0.0],
    )


def _retrieval_query_text(*, query: str, character: Character) -> str:
    aliases = ", ".join(character.aliases) if character.aliases else "none"
    return "\n".join(
        [
            f"character: {character.canonical_name}",
            f"aliases: {aliases}",
            "user_query:",
            query,
        ]
    )


def _character_anchor_chunks(
    chunks: list[SourceChunk],
    *,
    character: Character,
    limit: int,
) -> list[SourceChunk]:
    anchors = [character.canonical_name, *character.aliases]
    anchored = [
        chunk
        for chunk in chunks
        if any(anchor and anchor in chunk.text for anchor in anchors)
    ]
    return anchored[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
