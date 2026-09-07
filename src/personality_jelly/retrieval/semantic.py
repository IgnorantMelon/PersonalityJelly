from __future__ import annotations

from dataclasses import dataclass
import math

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import Character, SourceChunk, SourceChunkEmbedding
from personality_jelly.llm import EmbeddingConfig, LLMProvider
from personality_jelly.storage import SourceChunkEmbeddingRepository, SourceChunkRepository


@dataclass(frozen=True)
class RetrievedSourceChunk:
    chunk: SourceChunk
    rank: int
    score: float | None = None


@dataclass(frozen=True)
class SourceRetrievalResult:
    results: list[RetrievedSourceChunk]

    @property
    def chunks(self) -> list[SourceChunk]:
        return [result.chunk for result in self.results]


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
        return SourceRetrievalResult(results=[])

    if provider is None or embedding_config is None:
        return SourceRetrievalResult(
            results=[
                RetrievedSourceChunk(chunk=chunk, rank=index)
                for index, chunk in enumerate(
                    _character_anchor_chunks(chunks, character=character, limit=limit),
                    start=1,
                )
            ],
        )

    query_text = _retrieval_query_text(query=query, character=character)
    query_embedding = provider.embed_texts(
        [query_text],
        embedding_config=embedding_config,
    )[0]
    chunk_embeddings = _load_or_create_chunk_embeddings(
        session,
        chunks=chunks,
        provider=provider,
        embedding_config=embedding_config,
    )
    scored = [
        (_cosine_similarity(query_embedding, chunk_embedding), index, chunk)
        for index, chunk in enumerate(chunks)
        for chunk_embedding in [chunk_embeddings[chunk.id]]
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return SourceRetrievalResult(
        results=[
            RetrievedSourceChunk(chunk=chunk, rank=rank, score=score)
            for rank, (score, _, chunk) in enumerate(scored[:limit], start=1)
            if score > 0.0
        ],
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


def _load_or_create_chunk_embeddings(
    session: Session,
    *,
    chunks: list[SourceChunk],
    provider: LLMProvider,
    embedding_config: EmbeddingConfig,
) -> dict[str, list[float]]:
    repository = SourceChunkEmbeddingRepository(session)
    existing_embeddings = repository.list_for_chunks(
        [chunk.id for chunk in chunks],
        embedding_model=embedding_config.model,
    )
    embeddings_by_chunk_id = {
        embedding.source_chunk_id: embedding.embedding
        for embedding in existing_embeddings
    }
    missing_chunks = [
        chunk for chunk in chunks if chunk.id not in embeddings_by_chunk_id
    ]
    if not missing_chunks:
        return embeddings_by_chunk_id

    generated_embeddings = provider.embed_texts(
        [chunk.text for chunk in missing_chunks],
        embedding_config=embedding_config,
    )
    new_embeddings = [
        SourceChunkEmbedding(
            id=generate_id(EntityKind.SOURCE_CHUNK_EMBEDDING),
            source_chunk_id=chunk.id,
            embedding_model=embedding_config.model,
            embedding=embedding,
        )
        for chunk, embedding in zip(missing_chunks, generated_embeddings, strict=True)
    ]
    repository.add_many(new_embeddings)
    embeddings_by_chunk_id.update(
        {
            embedding.source_chunk_id: embedding.embedding
            for embedding in new_embeddings
        }
    )
    return embeddings_by_chunk_id


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
