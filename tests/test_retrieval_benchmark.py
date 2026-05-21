from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    EvidenceRef,
    SourceWork,
)
from personality_jelly.evaluation import (
    RetrievalBenchmarkCase,
    run_retrieval_benchmark,
    summarize_retrieval_benchmark,
)
from personality_jelly.ingestion import chunk_source_text
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    EvidenceRefRepository,
    RetrievalEvaluationCaseResultRepository,
    RetrievalEvaluationRunRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class RetrievalEmbeddingProvider:
    name = "retrieval-embedding-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        return [_vector_for_text(text) for text in texts]


def test_run_retrieval_benchmark_persists_ranking_and_empty_result_metrics() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Retrieval Work", source_type="markdown")
        )
        chunks = chunk_source_text(
            "sw_001",
            "\n\n".join(
                [
                    "Lin Shuang watches the window before making a decision.",
                    "The bell rings over an empty street.",
                    "Lin Shuang studies rain shadows before acting.",
                ]
            ),
        )
        SourceChunkRepository(session).add_many(chunks)
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )
        CanonClaimRepository(session).add(
            CanonClaim(
                id="claim_001",
                source_work_id="sw_001",
                character_id="char_001",
                claim_type=ClaimType.PERSONALITY,
                content="Lin Shuang observes carefully before acting.",
                status=ClaimStatus.VERIFIED,
                confidence=0.9,
                created_by="reader",
            )
        )
        EvidenceRefRepository(session).add(
            EvidenceRef(
                id="ev_001",
                claim_id="claim_001",
                chunk_id=chunks[0].id,
                excerpt=chunks[0].text,
                support_score=0.95,
            )
        )

        result = run_retrieval_benchmark(
            session,
            character_id="char_001",
            provider=RetrievalEmbeddingProvider(),
            embedding_config=EmbeddingConfig(model="fake-embedding"),
            test_suite="retrieval_suite",
            include_empty_case=True,
        )
        session.commit()

    with session_factory() as session:
        run = RetrievalEvaluationRunRepository(session).require(result.run.id)
        case_results = RetrievalEvaluationCaseResultRepository(session).list_by_run(run.id)

    assert run.status == "completed"
    assert run.test_suite == "retrieval_suite"
    assert run.embedding_model == "fake-embedding"
    assert run.total_cases == 2
    assert run.passed_cases == 1
    assert run.failed_cases == 1
    assert case_results[0].case_id == "claim_1"
    assert case_results[0].status == "passed"
    assert case_results[0].recall == 1.0
    assert case_results[0].first_relevant_rank == 1
    assert case_results[0].retrieved_chunk_ids[0] == chunks[0].id
    assert case_results[1].case_id == "empty_result"
    assert case_results[1].status == "failed"
    assert "Expected no source chunks" in case_results[1].reasons[0]

    report = summarize_retrieval_benchmark(case_results)
    assert report.total_cases == 2
    assert report.evidence_case_count == 1
    assert report.empty_case_count == 1
    assert report.pass_rate == 0.5
    assert report.evidence_pass_rate == 1.0
    assert report.empty_pass_rate == 0.0
    assert report.average_recall == 1.0
    assert report.average_ranking_score == 1.0
    assert report.first_relevant_at_one_count == 1
    assert report.no_relevant_result_count == 0
    assert report.retrieved_empty_when_expected_empty_count == 0
    assert report.retrieved_nonempty_when_expected_empty_count == 1
    assert report.missing_expected_chunk_count == 0


def test_run_retrieval_benchmark_supports_explicit_cases() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Explicit Cases", source_type="markdown")
        )
        chunks = chunk_source_text(
            "sw_001",
            "Lin Shuang watches the window before making a decision.",
        )
        SourceChunkRepository(session).add_many(chunks)
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )

        result = run_retrieval_benchmark(
            session,
            character_id="char_001",
            provider=RetrievalEmbeddingProvider(),
            embedding_config=EmbeddingConfig(model="fake-embedding"),
            cases=(
                RetrievalBenchmarkCase(
                    id="manual",
                    query="How does Lin Shuang decide?",
                    expected_chunk_ids=(chunks[0].id,),
                    limit=1,
                ),
            ),
        )

    assert result.run.total_cases == 1
    assert result.run.passed_cases == 1
    assert result.case_results[0].case_id == "manual"


def test_summarize_retrieval_benchmark_reports_missing_expected_chunks() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Missing Evidence", source_type="markdown")
        )
        chunks = chunk_source_text(
            "sw_001",
            "\n\n".join(
                [
                    "Lin Shuang watches the window before making a decision.",
                    "The bell rings over an empty street.",
                ]
            ),
        )
        SourceChunkRepository(session).add_many(chunks)
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )

        result = run_retrieval_benchmark(
            session,
            character_id="char_001",
            provider=RetrievalEmbeddingProvider(),
            embedding_config=EmbeddingConfig(model="fake-embedding"),
            cases=(
                RetrievalBenchmarkCase(
                    id="missing",
                    query="No matching source evidence should be retrieved.",
                    expected_chunk_ids=("chunk_missing_a", "chunk_missing_b"),
                    limit=1,
                ),
                RetrievalBenchmarkCase(
                    id="empty",
                    query="Out-of-scope retrieval probe with no expected source evidence.",
                    expected_chunk_ids=(),
                    limit=1,
                ),
            ),
        )

    report = summarize_retrieval_benchmark(result.case_results)

    assert result.run.total_cases == 2
    assert result.run.passed_cases == 0
    assert report.total_cases == 2
    assert report.evidence_case_count == 1
    assert report.empty_case_count == 1
    assert report.pass_rate == 0.0
    assert report.evidence_failed_cases == 1
    assert report.empty_failed_cases == 1
    assert report.average_recall == 0.0
    assert report.no_relevant_result_count == 1
    assert report.missing_expected_chunk_count == 2
    assert report.retrieved_nonempty_when_expected_empty_count == 1


def _vector_for_text(text: str) -> list[float]:
    if "Out-of-scope retrieval probe" in text:
        return [0.3, 0.0]
    if "user_query" in text:
        return [1.0, 0.0]
    if text == "Lin Shuang watches the window before making a decision.":
        return [0.95, 0.05]
    if text == "Lin Shuang studies rain shadows before acting.":
        return [0.8, 0.2]
    return [0.0, 1.0]
