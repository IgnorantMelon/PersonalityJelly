from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
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


class _RetrievalBenchmarkCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    query: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=4, gt=0)

    @field_validator("id", "query", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("expected_chunk_ids")
    @classmethod
    def _normalize_expected_chunk_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for chunk_id in value:
            stripped = chunk_id.strip()
            if not stripped:
                raise ValueError("expected_chunk_ids must not contain blank values")
            normalized.append(stripped)
        return normalized


class _RetrievalBenchmarkCasesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[_RetrievalBenchmarkCaseSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_case_ids(self) -> _RetrievalBenchmarkCasesFile:
        seen: set[str] = set()
        duplicate_ids: list[str] = []
        for benchmark_case in self.cases:
            if benchmark_case.id in seen:
                duplicate_ids.append(benchmark_case.id)
            seen.add(benchmark_case.id)
        if duplicate_ids:
            unique_duplicates = ", ".join(dict.fromkeys(duplicate_ids))
            raise ValueError(f"duplicate retrieval benchmark case ids: {unique_duplicates}")
        return self


@dataclass(frozen=True)
class RetrievalBenchmarkRunResult:
    run: RetrievalEvaluationRun
    case_results: list[RetrievalEvaluationCaseResult]


@dataclass(frozen=True)
class RetrievalBenchmarkReport:
    total_cases: int
    evidence_case_count: int
    empty_case_count: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    evidence_passed_cases: int
    evidence_failed_cases: int
    evidence_pass_rate: float
    empty_passed_cases: int
    empty_failed_cases: int
    empty_pass_rate: float
    average_recall: float
    average_ranking_score: float
    first_relevant_at_one_count: int
    no_relevant_result_count: int
    retrieved_empty_when_expected_empty_count: int
    retrieved_nonempty_when_expected_empty_count: int
    missing_expected_chunk_count: int


@dataclass(frozen=True)
class RetrievalBenchmarkCasesSummary:
    total_cases: int
    evidence_case_count: int
    empty_case_count: int
    expected_chunk_ref_count: int
    min_limit: int
    max_limit: int


def summarize_retrieval_benchmark_cases(
    cases: tuple[RetrievalBenchmarkCase, ...],
) -> RetrievalBenchmarkCasesSummary:
    if not cases:
        raise ValueError("cases must not be empty")
    evidence_cases = [
        benchmark_case
        for benchmark_case in cases
        if benchmark_case.expected_chunk_ids
    ]
    return RetrievalBenchmarkCasesSummary(
        total_cases=len(cases),
        evidence_case_count=len(evidence_cases),
        empty_case_count=len(cases) - len(evidence_cases),
        expected_chunk_ref_count=sum(
            len(benchmark_case.expected_chunk_ids)
            for benchmark_case in cases
        ),
        min_limit=min(benchmark_case.limit for benchmark_case in cases),
        max_limit=max(benchmark_case.limit for benchmark_case in cases),
    )


def load_retrieval_benchmark_cases_file(
    path: Path | str,
) -> tuple[RetrievalBenchmarkCase, ...]:
    case_file = Path(path)
    try:
        payload = json.loads(case_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Retrieval benchmark cases file not found: {case_file}") from exc
    except OSError as exc:
        message = f"Unable to read retrieval benchmark cases file {case_file}: {exc}"
        raise ValueError(message) from exc
    except json.JSONDecodeError as exc:
        message = (
            f"Invalid retrieval benchmark cases JSON in {case_file}: "
            f"{exc.msg} at line {exc.lineno} column {exc.colno}"
        )
        raise ValueError(message) from exc

    try:
        cases_file = _RetrievalBenchmarkCasesFile.model_validate(payload)
    except ValidationError as exc:
        message = _format_cases_file_validation_error(exc)
        raise ValueError(f"Invalid retrieval benchmark cases file {case_file}: {message}") from exc

    return tuple(
        RetrievalBenchmarkCase(
            id=benchmark_case.id,
            query=benchmark_case.query,
            expected_chunk_ids=tuple(benchmark_case.expected_chunk_ids),
            limit=benchmark_case.limit,
        )
        for benchmark_case in cases_file.cases
    )


def export_retrieval_benchmark_cases_file(
    path: Path | str,
    cases: tuple[RetrievalBenchmarkCase, ...],
    *,
    append: bool = False,
    overwrite: bool = False,
) -> Path:
    case_file = Path(path)
    if append:
        cases = _merge_retrieval_benchmark_cases(
            load_retrieval_benchmark_cases_file(case_file) if case_file.exists() else (),
            cases,
            overwrite=overwrite,
        )
    elif case_file.exists() and not overwrite:
        raise ValueError(
            f"Retrieval benchmark cases file already exists: {case_file}. "
            "Use --append-cases-file to add cases or --overwrite-cases-file to replace it."
        )

    payload = {
        "cases": [
            {
                "id": benchmark_case.id,
                "query": benchmark_case.query,
                "expected_chunk_ids": list(benchmark_case.expected_chunk_ids),
                "limit": benchmark_case.limit,
            }
            for benchmark_case in cases
        ]
    }
    try:
        cases_file = _RetrievalBenchmarkCasesFile.model_validate(payload)
    except ValidationError as exc:
        message = _format_cases_file_validation_error(exc)
        raise ValueError(f"Cannot export retrieval benchmark cases: {message}") from exc

    try:
        case_file.parent.mkdir(parents=True, exist_ok=True)
        case_file.write_text(
            json.dumps(cases_file.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        message = f"Unable to write retrieval benchmark cases file {case_file}: {exc}"
        raise ValueError(message) from exc
    return case_file


def _merge_retrieval_benchmark_cases(
    existing_cases: tuple[RetrievalBenchmarkCase, ...],
    new_cases: tuple[RetrievalBenchmarkCase, ...],
    *,
    overwrite: bool,
) -> tuple[RetrievalBenchmarkCase, ...]:
    merged_by_id = {benchmark_case.id: benchmark_case for benchmark_case in existing_cases}
    duplicate_ids = [
        benchmark_case.id
        for benchmark_case in new_cases
        if benchmark_case.id in merged_by_id
    ]
    if duplicate_ids and not overwrite:
        unique_duplicates = ", ".join(dict.fromkeys(duplicate_ids))
        raise ValueError(
            "Retrieval benchmark cases file already contains case ids: "
            f"{unique_duplicates}. Use --overwrite-cases-file to replace duplicates."
        )
    for benchmark_case in new_cases:
        merged_by_id[benchmark_case.id] = benchmark_case
    return tuple(merged_by_id.values())


def build_retrieval_benchmark_cases_from_results(
    case_results: list[RetrievalEvaluationCaseResult],
    *,
    failed_only: bool = False,
    limit: int = 4,
) -> tuple[RetrievalBenchmarkCase, ...]:
    if limit < 1:
        raise ValueError("limit must be greater than 0")

    cases: list[RetrievalBenchmarkCase] = []
    for case_result in case_results:
        if failed_only and case_result.status != EvaluationCaseStatus.FAILED:
            continue
        cases.append(
            RetrievalBenchmarkCase(
                id=case_result.case_id,
                query=case_result.query,
                expected_chunk_ids=tuple(case_result.expected_chunk_ids),
                limit=limit,
            )
        )
    if not cases:
        raise ValueError("No retrieval benchmark case results matched the export filters")
    return tuple(cases)


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


def summarize_retrieval_benchmark(
    case_results: list[RetrievalEvaluationCaseResult],
) -> RetrievalBenchmarkReport:
    total_cases = len(case_results)
    evidence_results = [
        case_result
        for case_result in case_results
        if case_result.expected_chunk_ids
    ]
    empty_results = [
        case_result
        for case_result in case_results
        if not case_result.expected_chunk_ids
    ]
    passed_cases = _count_passed(case_results)
    failed_cases = total_cases - passed_cases
    evidence_passed_cases = _count_passed(evidence_results)
    evidence_failed_cases = len(evidence_results) - evidence_passed_cases
    empty_passed_cases = _count_passed(empty_results)
    empty_failed_cases = len(empty_results) - empty_passed_cases
    missing_expected_chunk_count = sum(
        len(
            set(case_result.expected_chunk_ids)
            - set(case_result.retrieved_chunk_ids)
        )
        for case_result in evidence_results
    )

    return RetrievalBenchmarkReport(
        total_cases=total_cases,
        evidence_case_count=len(evidence_results),
        empty_case_count=len(empty_results),
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=_ratio(passed_cases, total_cases),
        evidence_passed_cases=evidence_passed_cases,
        evidence_failed_cases=evidence_failed_cases,
        evidence_pass_rate=_ratio(evidence_passed_cases, len(evidence_results)),
        empty_passed_cases=empty_passed_cases,
        empty_failed_cases=empty_failed_cases,
        empty_pass_rate=_ratio(empty_passed_cases, len(empty_results)),
        average_recall=_average([case_result.recall for case_result in evidence_results]),
        average_ranking_score=_average(
            [case_result.ranking_score for case_result in evidence_results]
        ),
        first_relevant_at_one_count=sum(
            1
            for case_result in evidence_results
            if case_result.first_relevant_rank == 1
        ),
        no_relevant_result_count=sum(
            1
            for case_result in evidence_results
            if case_result.first_relevant_rank is None
        ),
        retrieved_empty_when_expected_empty_count=sum(
            1
            for case_result in empty_results
            if not case_result.retrieved_chunk_ids
        ),
        retrieved_nonempty_when_expected_empty_count=sum(
            1
            for case_result in empty_results
            if case_result.retrieved_chunk_ids
        ),
        missing_expected_chunk_count=missing_expected_chunk_count,
    )


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


def _count_passed(case_results: list[RetrievalEvaluationCaseResult]) -> int:
    return sum(
        1
        for case_result in case_results
        if case_result.status == EvaluationCaseStatus.PASSED
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _format_cases_file_validation_error(error: ValidationError) -> str:
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "cases"
        messages.append(f"{location}: {item['msg']}")
    return "; ".join(messages)
