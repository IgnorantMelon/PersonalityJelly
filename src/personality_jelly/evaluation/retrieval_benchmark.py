from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    ClaimStatus,
    EvaluationCaseStatus,
    EvaluationStatus,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRun,
)
from personality_jelly.domain.models import utc_now
from personality_jelly.llm import EmbeddingConfig, LLMProvider
from personality_jelly.retrieval import retrieve_source_chunks
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    EvidenceRefRepository,
    RetrievalEvaluationCaseResultRepository,
    RetrievalEvaluationRunRepository,
)


DEFAULT_RETRIEVAL_TEST_SUITE = "retrieval_default"
DEFAULT_EMPTY_RETRIEVAL_QUERY = (
    "Out-of-scope retrieval probe with no expected source evidence."
)


@dataclass(frozen=True)
class RetrievalBenchmarkCase:
    id: str
    query: str
    expected_chunk_ids: tuple[str, ...]
    limit: int = 4


@dataclass(frozen=True)
class RetrievalBenchmarkRunResult:
    run: RetrievalEvaluationRun
    case_results: list[RetrievalEvaluationCaseResult]


def build_default_retrieval_benchmark_cases(
    session: Session,
    *,
    character_id: str,
    max_cases: int = 20,
    include_empty_case: bool = True,
) -> tuple[RetrievalBenchmarkCase, ...]:
    if max_cases < 1:
        raise ValueError("max_cases must be greater than 0")

    claims = CanonClaimRepository(session).list_by_character(
        character_id,
        status=ClaimStatus.VERIFIED,
    )
    evidence_repository = EvidenceRefRepository(session)
    cases: list[RetrievalBenchmarkCase] = []
    for claim in claims:
        expected_chunk_ids = tuple(
            dict.fromkeys(
                evidence.chunk_id
                for evidence in evidence_repository.list_by_claim(claim.id)
            )
        )
        if not expected_chunk_ids:
            continue
        cases.append(
            RetrievalBenchmarkCase(
                id=f"claim_{len(cases) + 1}",
                query=claim.content,
                expected_chunk_ids=expected_chunk_ids,
            )
        )
        if len(cases) >= max_cases:
            break

    if include_empty_case:
        cases.append(
            RetrievalBenchmarkCase(
                id="empty_result",
                query=DEFAULT_EMPTY_RETRIEVAL_QUERY,
                expected_chunk_ids=(),
            )
        )
    if not cases:
        raise ValueError(
            f"Character {character_id!r} has no verified claims with evidence refs"
        )
    return tuple(cases)


def run_retrieval_benchmark(
    session: Session,
    *,
    character_id: str,
    provider: LLMProvider | None = None,
    embedding_config: EmbeddingConfig | None = None,
    test_suite: str = DEFAULT_RETRIEVAL_TEST_SUITE,
    cases: tuple[RetrievalBenchmarkCase, ...] | None = None,
    max_cases: int = 20,
    include_empty_case: bool = True,
) -> RetrievalBenchmarkRunResult:
    character = CharacterRepository(session).require(character_id)
    benchmark_cases = cases or build_default_retrieval_benchmark_cases(
        session,
        character_id=character.id,
        max_cases=max_cases,
        include_empty_case=include_empty_case,
    )
    run_repository = RetrievalEvaluationRunRepository(session)
    run = RetrievalEvaluationRun(
        id=generate_id(EntityKind.RETRIEVAL_EVALUATION_RUN),
        source_work_id=character.source_work_id,
        character_id=character.id,
        test_suite=test_suite,
        total_cases=len(benchmark_cases),
        embedding_model=embedding_config.model if embedding_config is not None else None,
    )
    run_repository.add(run)

    case_repository = RetrievalEvaluationCaseResultRepository(session)
    case_results: list[RetrievalEvaluationCaseResult] = []
    for benchmark_case in benchmark_cases:
        retrieval = retrieve_source_chunks(
            session,
            source_work_id=character.source_work_id,
            character=character,
            query=benchmark_case.query,
            limit=benchmark_case.limit,
            provider=provider,
            embedding_config=embedding_config,
        )
        result = _evaluate_retrieval_case(
            run_id=run.id,
            benchmark_case=benchmark_case,
            retrieved_chunk_ids=[item.chunk.id for item in retrieval.results],
            retrieved_scores=[item.score for item in retrieval.results],
        )
        case_repository.add(result)
        case_results.append(result)

    passed_cases = sum(
        1 for case_result in case_results
        if case_result.status == EvaluationCaseStatus.PASSED
    )
    failed_cases = len(case_results) - passed_cases
    run = run_repository.update_summary(
        run.id,
        status=EvaluationStatus.COMPLETED,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        completed_at=utc_now(),
    )
    return RetrievalBenchmarkRunResult(run=run, case_results=case_results)


def _evaluate_retrieval_case(
    *,
    run_id: str,
    benchmark_case: RetrievalBenchmarkCase,
    retrieved_chunk_ids: list[str],
    retrieved_scores: list[float | None],
) -> RetrievalEvaluationCaseResult:
    expected = set(benchmark_case.expected_chunk_ids)
    if not expected:
        passed = not retrieved_chunk_ids
        return RetrievalEvaluationCaseResult(
            id=generate_id(EntityKind.RETRIEVAL_EVALUATION_CASE_RESULT),
            run_id=run_id,
            case_id=benchmark_case.id,
            query=benchmark_case.query,
            expected_chunk_ids=[],
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_scores=retrieved_scores,
            status=(
                EvaluationCaseStatus.PASSED
                if passed
                else EvaluationCaseStatus.FAILED
            ),
            recall=1.0 if passed else 0.0,
            first_relevant_rank=None,
            ranking_score=1.0 if passed else 0.0,
            reasons=[
                "No source chunks were expected and retrieval returned none."
                if passed
                else "Expected no source chunks, but retrieval returned chunks."
            ],
        )

    matched = [chunk_id for chunk_id in retrieved_chunk_ids if chunk_id in expected]
    recall = len(set(matched)) / len(expected)
    first_relevant_rank = next(
        (
            index
            for index, chunk_id in enumerate(retrieved_chunk_ids, start=1)
            if chunk_id in expected
        ),
        None,
    )
    ranking_score = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0
    passed = recall == 1.0 and first_relevant_rank == 1
    reasons = [
        f"recall={recall:.3f}",
        f"first_relevant_rank={first_relevant_rank or 'none'}",
        f"ranking_score={ranking_score:.3f}",
    ]
    if not passed:
        missing = [
            chunk_id
            for chunk_id in benchmark_case.expected_chunk_ids
            if chunk_id not in matched
        ]
        if missing:
            reasons.append(f"missing_expected_chunk_ids={','.join(missing)}")
        if first_relevant_rank != 1:
            reasons.append("top-ranked chunk was not an expected evidence chunk")

    return RetrievalEvaluationCaseResult(
        id=generate_id(EntityKind.RETRIEVAL_EVALUATION_CASE_RESULT),
        run_id=run_id,
        case_id=benchmark_case.id,
        query=benchmark_case.query,
        expected_chunk_ids=list(benchmark_case.expected_chunk_ids),
        retrieved_chunk_ids=retrieved_chunk_ids,
        retrieved_scores=retrieved_scores,
        status=EvaluationCaseStatus.PASSED if passed else EvaluationCaseStatus.FAILED,
        recall=recall,
        first_relevant_rank=first_relevant_rank,
        ranking_score=ranking_score,
        reasons=reasons,
    )
