import json
from pathlib import Path

from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    EvidenceRef,
    SourceChunk,
    SourceWork,
)
from personality_jelly.evaluation import (
    RetrievalBenchmarkCase,
    build_retrieval_benchmark_cases_from_results,
    export_retrieval_benchmark_cases_file,
    load_retrieval_benchmark_cases_file,
    run_retrieval_benchmark,
    summarize_retrieval_benchmark_cases,
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


BENCHMARK_ASSETS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"


class RetrievalEmbeddingProvider:
    name = "retrieval-embedding-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        return [_vector_for_text(text) for text in texts]


class QualityRegressionEmbeddingProvider:
    name = "quality-regression-embedding-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        return [_quality_regression_vector_for_text(text) for text in texts]


def test_summarize_retrieval_benchmark_cases_reports_case_shape() -> None:
    summary = summarize_retrieval_benchmark_cases(
        (
            RetrievalBenchmarkCase(
                id="evidence",
                query="Evidence query.",
                expected_chunk_ids=("chunk_a", "chunk_b"),
                limit=2,
            ),
            RetrievalBenchmarkCase(
                id="empty",
                query="Empty query.",
                expected_chunk_ids=(),
                limit=5,
            ),
        )
    )

    assert summary.total_cases == 2
    assert summary.evidence_case_count == 1
    assert summary.empty_case_count == 1
    assert summary.expected_chunk_ref_count == 2
    assert summary.min_limit == 2
    assert summary.max_limit == 5


def test_load_retrieval_benchmark_cases_file_normalizes_explicit_cases(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    cases_file.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": " manual_evidence ",
                        "query": " How does Lin Shuang decide? ",
                        "expected_chunk_ids": [" chunk_a ", "chunk_b"],
                        "limit": 2,
                    },
                    {
                        "id": "manual_empty",
                        "query": "Out-of-scope probe.",
                        "expected_chunk_ids": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_retrieval_benchmark_cases_file(cases_file)

    assert cases == (
        RetrievalBenchmarkCase(
            id="manual_evidence",
            query="How does Lin Shuang decide?",
            expected_chunk_ids=("chunk_a", "chunk_b"),
            limit=2,
        ),
        RetrievalBenchmarkCase(
            id="manual_empty",
            query="Out-of-scope probe.",
            expected_chunk_ids=(),
            limit=4,
        ),
    )


def test_committed_retrieval_benchmark_asset_loads_through_loader() -> None:
    cases = load_retrieval_benchmark_cases_file(
        BENCHMARK_ASSETS_DIR / "retrieval" / "evidence-smoke.json"
    )

    assert cases == (
        RetrievalBenchmarkCase(
            id="evidence_smoke_observation_query",
            query="How does Lin Shuang decide before acting?",
            expected_chunk_ids=("sample_chunk_observation",),
            limit=3,
        ),
    )


def test_committed_retrieval_quality_regression_cases_cover_diagnostics() -> None:
    cases = load_retrieval_benchmark_cases_file(
        BENCHMARK_ASSETS_DIR / "retrieval" / "retrieval-quality-regression.json"
    )
    summary = summarize_retrieval_benchmark_cases(cases)
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_quality", title="Retrieval Quality", source_type="markdown")
        )
        SourceChunkRepository(session).add_many(
            [
                SourceChunk(
                    id="quality_chunk_observation",
                    source_work_id="sw_quality",
                    paragraph_index=0,
                    text="Lin Shuang watches the window before making a decision.",
                ),
                SourceChunk(
                    id="quality_chunk_rain",
                    source_work_id="sw_quality",
                    paragraph_index=1,
                    text="Lin Shuang studies rain shadows before acting.",
                ),
                SourceChunk(
                    id="quality_chunk_bell",
                    source_work_id="sw_quality",
                    paragraph_index=2,
                    text="The bell rings over an empty street.",
                ),
            ]
        )
        CharacterRepository(session).add(
            Character(
                id="char_quality",
                source_work_id="sw_quality",
                canonical_name="Lin Shuang",
            )
        )

        result = run_retrieval_benchmark(
            session,
            character_id="char_quality",
            provider=QualityRegressionEmbeddingProvider(),
            embedding_config=EmbeddingConfig(model="quality-regression-embedding"),
            test_suite="retrieval_quality_regression",
            cases=cases,
        )

    results_by_case_id = {
        case_result.case_id: case_result
        for case_result in result.case_results
    }
    report = summarize_retrieval_benchmark(result.case_results)

    assert summary.total_cases == 5
    assert summary.evidence_case_count == 4
    assert summary.empty_case_count == 1
    assert summary.expected_chunk_ref_count == 5
    assert summary.min_limit == 1
    assert summary.max_limit == 3
    assert result.run.total_cases == 5
    assert result.run.passed_cases == 3
    assert result.run.failed_cases == 2

    single = results_by_case_id["quality_single_expected_observation"]
    assert single.status == "passed"
    assert single.recall == 1.0
    assert single.first_relevant_rank == 1
    assert single.retrieved_chunk_ids == ["quality_chunk_observation"]

    multi = results_by_case_id["quality_multi_expected_observation_rain"]
    assert multi.status == "passed"
    assert multi.recall == 1.0
    assert multi.first_relevant_rank == 1
    assert multi.retrieved_chunk_ids == [
        "quality_chunk_observation",
        "quality_chunk_rain",
    ]

    empty = results_by_case_id["quality_empty_out_of_scope"]
    assert empty.status == "passed"
    assert empty.retrieved_chunk_ids == []
    assert empty.recall == 1.0
    assert empty.ranking_score == 1.0
    assert "No source chunks were expected" in empty.reasons[0]

    missing = results_by_case_id["quality_missing_expected_chunk"]
    assert missing.status == "failed"
    assert missing.recall == 0.0
    assert missing.first_relevant_rank is None
    assert missing.retrieved_chunk_ids == ["quality_chunk_bell"]
    assert "missing_expected_chunk_ids=quality_chunk_missing" in missing.reasons
    assert "top_retrieved_chunk_id=quality_chunk_bell" in missing.reasons
    assert "top-ranked chunk was not an expected evidence chunk" in missing.reasons

    top_wrong = results_by_case_id["quality_top_wrong_ranking"]
    assert top_wrong.status == "failed"
    assert top_wrong.recall == 1.0
    assert top_wrong.first_relevant_rank == 2
    assert top_wrong.ranking_score == 0.5
    assert top_wrong.retrieved_chunk_ids == [
        "quality_chunk_observation",
        "quality_chunk_rain",
    ]
    assert "missing_expected_chunk_ids=none" in top_wrong.reasons
    assert "top_retrieved_chunk_id=quality_chunk_observation" in top_wrong.reasons
    assert "top_retrieved_chunk_expected=false" in top_wrong.reasons

    assert report.total_cases == 5
    assert report.evidence_case_count == 4
    assert report.empty_case_count == 1
    assert report.pass_rate == 0.6
    assert report.evidence_pass_rate == 0.5
    assert report.empty_pass_rate == 1.0
    assert report.average_recall == 0.75
    assert report.average_ranking_score == 0.625
    assert report.first_relevant_at_one_count == 2
    assert report.no_relevant_result_count == 1
    assert report.retrieved_empty_when_expected_empty_count == 1
    assert report.retrieved_nonempty_when_expected_empty_count == 0
    assert report.missing_expected_chunk_count == 1


def test_load_retrieval_benchmark_cases_file_rejects_duplicate_case_ids(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    cases_file.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "manual",
                        "query": "First query.",
                        "expected_chunk_ids": ["chunk_a"],
                    },
                    {
                        "id": "manual",
                        "query": "Second query.",
                        "expected_chunk_ids": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        load_retrieval_benchmark_cases_file(cases_file)
    except ValueError as error:
        assert "duplicate retrieval benchmark case ids: manual" in str(error)
    else:
        raise AssertionError("Expected duplicate retrieval benchmark case ids to be rejected")


def test_load_retrieval_benchmark_cases_file_rejects_empty_cases(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    cases_file.write_text(json.dumps({"cases": []}), encoding="utf-8")

    try:
        load_retrieval_benchmark_cases_file(cases_file)
    except ValueError as error:
        assert "cases: List should have at least 1 item" in str(error)
    else:
        raise AssertionError("Expected empty retrieval benchmark cases to be rejected")


def test_export_retrieval_benchmark_cases_file_round_trips_cases(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "nested" / "retrieval-cases.json"
    cases = (
        RetrievalBenchmarkCase(
            id="manual_evidence",
            query="How does Lin Shuang decide?",
            expected_chunk_ids=("chunk_a",),
            limit=2,
        ),
        RetrievalBenchmarkCase(
            id="manual_empty",
            query="Out-of-scope probe.",
            expected_chunk_ids=(),
        ),
    )

    exported_path = export_retrieval_benchmark_cases_file(cases_file, cases)

    payload = json.loads(cases_file.read_text(encoding="utf-8"))
    assert exported_path == cases_file
    assert payload["cases"][0]["id"] == "manual_evidence"
    assert payload["cases"][0]["expected_chunk_ids"] == ["chunk_a"]
    assert payload["cases"][1]["limit"] == 4
    assert load_retrieval_benchmark_cases_file(cases_file) == cases


def test_export_retrieval_benchmark_cases_file_refuses_existing_file(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    cases_file.write_text("{}", encoding="utf-8")
    cases = (
        RetrievalBenchmarkCase(
            id="manual",
            query="How does Lin Shuang decide?",
            expected_chunk_ids=("chunk_a",),
        ),
    )

    try:
        export_retrieval_benchmark_cases_file(cases_file, cases)
    except ValueError as error:
        assert "already exists" in str(error)
        assert "--overwrite-cases-file" in str(error)
    else:
        raise AssertionError("Expected export to refuse an existing cases file")

    export_retrieval_benchmark_cases_file(cases_file, cases, overwrite=True)

    assert load_retrieval_benchmark_cases_file(cases_file) == cases


def test_export_retrieval_benchmark_cases_file_appends_to_existing_file(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    export_retrieval_benchmark_cases_file(
        cases_file,
        (
            RetrievalBenchmarkCase(
                id="existing",
                query="Existing query.",
                expected_chunk_ids=("chunk_existing",),
            ),
        ),
    )

    export_retrieval_benchmark_cases_file(
        cases_file,
        (
            RetrievalBenchmarkCase(
                id="new",
                query="New query.",
                expected_chunk_ids=("chunk_new",),
                limit=2,
            ),
        ),
        append=True,
    )

    assert load_retrieval_benchmark_cases_file(cases_file) == (
        RetrievalBenchmarkCase(
            id="existing",
            query="Existing query.",
            expected_chunk_ids=("chunk_existing",),
        ),
        RetrievalBenchmarkCase(
            id="new",
            query="New query.",
            expected_chunk_ids=("chunk_new",),
            limit=2,
        ),
    )


def test_export_retrieval_benchmark_cases_file_append_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    cases_file = tmp_path / "retrieval-cases.json"
    export_retrieval_benchmark_cases_file(
        cases_file,
        (
            RetrievalBenchmarkCase(
                id="duplicate",
                query="Original query.",
                expected_chunk_ids=("chunk_original",),
            ),
            RetrievalBenchmarkCase(
                id="kept",
                query="Kept query.",
                expected_chunk_ids=("chunk_kept",),
            ),
        ),
    )

    replacement = (
        RetrievalBenchmarkCase(
            id="duplicate",
            query="Replacement query.",
            expected_chunk_ids=("chunk_replacement",),
            limit=2,
        ),
    )
    try:
        export_retrieval_benchmark_cases_file(cases_file, replacement, append=True)
    except ValueError as error:
        assert "already contains case ids: duplicate" in str(error)
        assert "--overwrite-cases-file" in str(error)
    else:
        raise AssertionError("Expected append export to reject duplicate case ids")

    export_retrieval_benchmark_cases_file(
        cases_file,
        replacement,
        append=True,
        overwrite=True,
    )

    assert load_retrieval_benchmark_cases_file(cases_file) == (
        replacement[0],
        RetrievalBenchmarkCase(
            id="kept",
            query="Kept query.",
            expected_chunk_ids=("chunk_kept",),
        ),
    )


def test_build_retrieval_benchmark_cases_from_results_filters_failed_cases() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Failure Export", source_type="markdown")
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
                    id="passing",
                    query="How does Lin Shuang decide?",
                    expected_chunk_ids=(chunks[0].id,),
                    limit=1,
                ),
                RetrievalBenchmarkCase(
                    id="failing",
                    query="Missing source evidence.",
                    expected_chunk_ids=("chunk_missing",),
                    limit=1,
                ),
            ),
        )

    cases = build_retrieval_benchmark_cases_from_results(
        result.case_results,
        failed_only=True,
        limit=3,
    )

    assert cases == (
        RetrievalBenchmarkCase(
            id="failing",
            query="Missing source evidence.",
            expected_chunk_ids=("chunk_missing",),
            limit=3,
        ),
    )


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
    assert "expected_count=0" in case_results[1].reasons
    assert "retrieved_count=2" in case_results[1].reasons
    assert f"top_retrieved_chunk_id={chunks[0].id}" in case_results[1].reasons
    assert "missing_expected_chunk_ids=none" in case_results[1].reasons
    assert "top_retrieved_chunk_expected=false" in case_results[1].reasons

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
    evidence_result = result.case_results[0]
    assert "expected_count=2" in evidence_result.reasons
    assert "retrieved_count=1" in evidence_result.reasons
    assert f"top_retrieved_chunk_id={chunks[0].id}" in evidence_result.reasons
    assert (
        "missing_expected_chunk_ids=chunk_missing_a,chunk_missing_b"
        in evidence_result.reasons
    )
    assert "top_retrieved_chunk_expected=false" in evidence_result.reasons
    assert "top-ranked chunk was not an expected evidence chunk" in evidence_result.reasons
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


def _quality_regression_vector_for_text(text: str) -> list[float]:
    ranking_probe = (
        "Which detail should rank the rain-shadow evidence below the window evidence?"
    )
    if text.endswith("How does Lin Shuang decide before acting?"):
        return [1.0, 0.0, 0.0]
    if text.endswith("Which details show how Lin Shuang observes before acting?"):
        return [1.0, 1.0, 0.0]
    if text.endswith("Out-of-scope retrieval probe with no expected source evidence."):
        return [0.0, 0.0, 0.0]
    if text.endswith("Which scene mentions missing archive evidence?"):
        return [0.0, 0.0, 1.0]
    if text.endswith(ranking_probe):
        return [1.0, 0.2, 0.0]
    if text == "Lin Shuang watches the window before making a decision.":
        return [1.0, 0.0, 0.0]
    if text == "Lin Shuang studies rain shadows before acting.":
        return [0.0, 1.0, 0.0]
    if text == "The bell rings over an empty street.":
        return [0.0, 0.0, 1.0]
    return [0.0, 0.0, 0.0]
