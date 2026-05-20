from personality_jelly.domain import Character, SourceWork
from personality_jelly.ingestion import chunk_source_text
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.retrieval import retrieve_source_chunks
from personality_jelly.storage import (
    CharacterRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class EmbeddingFakeProvider:
    name = "embedding-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        vectors = [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [0.8, 0.2],
        ]
        return vectors[: len(texts)]


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

        result = retrieve_source_chunks(
            session,
            source_work_id="sw_001",
            character=character,
            query="她为什么总是观察？",
            limit=2,
            provider=EmbeddingFakeProvider(),
            embedding_config=EmbeddingConfig(model="fake-embedding"),
        )

    assert len(result.chunks) == 2
    assert result.chunks[0].text == "林霜总是先观察，再行动。"
    assert result.chunks[1].text == "林霜在雨夜里观察窗外的影子。"
