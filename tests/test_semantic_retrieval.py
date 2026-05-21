from personality_jelly.domain import Character, SourceWork
from personality_jelly.ingestion import chunk_source_text
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.retrieval import retrieve_source_chunks
from personality_jelly.storage import (
    CharacterRepository,
    SourceChunkEmbeddingRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class EmbeddingFakeProvider:
    name = "embedding-fake"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        self.calls.append(texts)
        return [_vector_for_text(text) for text in texts]


def test_retrieve_source_chunks_ranks_by_embedding_similarity() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    text = "\n\n".join(
        [
            "林霜总是先观察，再行动。",
            "钟声响起时，旁人只看见空街。",
            "林霜在雨夜里观察窗外的影子。",
        ]
    )
    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="测试作品", source_type="markdown")
        )
        chunks = chunk_source_text("sw_001", text)
        SourceChunkRepository(session).add_many(chunks)
        character = Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="林霜",
            aliases=["霜"],
        )
        CharacterRepository(session).add(character)

        provider = EmbeddingFakeProvider()
        result = retrieve_source_chunks(
            session,
            source_work_id="sw_001",
            character=character,
            query="她为什么总是观察？",
            limit=2,
            provider=provider,
            embedding_config=EmbeddingConfig(model="fake-embedding"),
        )

    assert len(result.chunks) == 2
    assert result.chunks[0].text == "林霜总是先观察，再行动。"
    assert result.chunks[1].text == "林霜在雨夜里观察窗外的影子。"
    assert len(provider.calls) == 2
    assert len(provider.calls[0]) == 1
    assert len(provider.calls[1]) == 3


def test_retrieve_source_chunks_reuses_persisted_chunk_embeddings() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    text = "\n\n".join(
        [
            "林霜总是先观察，再行动。",
            "钟声响起时，旁人只看见空街。",
            "林霜在雨夜里观察窗外的影子。",
        ]
    )
    provider = EmbeddingFakeProvider()
    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="测试作品", source_type="markdown")
        )
        chunks = chunk_source_text("sw_001", text)
        SourceChunkRepository(session).add_many(chunks)
        character = Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="林霜",
            aliases=["霜"],
        )
        CharacterRepository(session).add(character)

        retrieve_source_chunks(
            session,
            source_work_id="sw_001",
            character=character,
            query="她为什么总是观察？",
            limit=2,
            provider=provider,
            embedding_config=EmbeddingConfig(model="fake-embedding"),
        )
        first_cached = SourceChunkEmbeddingRepository(session).list_for_chunks(
            [chunk.id for chunk in chunks],
            embedding_model="fake-embedding",
        )

        result = retrieve_source_chunks(
            session,
            source_work_id="sw_001",
            character=character,
            query="雨夜里发生了什么？",
            limit=2,
            provider=provider,
            embedding_config=EmbeddingConfig(model="fake-embedding"),
        )
        second_cached = SourceChunkEmbeddingRepository(session).list_for_chunks(
            [chunk.id for chunk in chunks],
            embedding_model="fake-embedding",
        )

    assert len(first_cached) == 3
    assert len(second_cached) == 3
    assert [len(call) for call in provider.calls] == [1, 3, 1]
    assert result.chunks


def _vector_for_text(text: str) -> list[float]:
    if "user_query" in text:
        return [1.0, 0.0]
    if text == "林霜总是先观察，再行动。":
        return [0.9, 0.1]
    if text == "林霜在雨夜里观察窗外的影子。":
        return [0.8, 0.2]
    return [0.0, 1.0]
