from __future__ import annotations

from typing import Literal

from pydantic import Field
from sqlalchemy.orm import Session

from personality_jelly.application.inspection import (
    BenchmarkModeDiagnostics,
    EvaluationRunDetail,
    InspectionModel,
    RetrievalEvaluationRunDetail,
    get_evaluation_run_detail,
    get_retrieval_evaluation_run_detail,
)
from personality_jelly.domain import InteractionMode
from personality_jelly.evaluation import (
    DEFAULT_BENCHMARK_CASE_SUITE,
    DEFAULT_RETRIEVAL_TEST_SUITE,
    BenchmarkCase,
    RetrievalBenchmarkCase,
    build_default_retrieval_benchmark_cases,
    get_benchmark_cases,
    run_ooc_benchmark,
    run_retrieval_benchmark,
    summarize_retrieval_benchmark_cases,
)
from personality_jelly.evaluation.benchmark import DEFAULT_OOC_TEST_SUITE
from personality_jelly.llm import EmbeddingConfig, LLMProvider, ModelConfig
from personality_jelly.storage import CharacterRepository, PersonaVersionRepository


class OOCBenchmarkCaseSummary(InspectionModel):
    id: str
    prompt: str
    interaction_mode: InteractionMode
    category: str


class OOCBenchmarkCasesSummary(InspectionModel):
    total_cases: int = Field(ge=0)
    mode_reports: list[BenchmarkModeDiagnostics] = Field(default_factory=list)


class OOCBenchmarkDryRunResult(InspectionModel):
    character_id: str
    persona_version_id: str
    case_suite: str | None = None
    cases_source: Literal["case_suite", "explicit"] = "case_suite"
    will_create_run: bool = False
    cases_summary: OOCBenchmarkCasesSummary
    cases: list[OOCBenchmarkCaseSummary] = Field(default_factory=list)


class RetrievalBenchmarkCaseSummary(InspectionModel):
    id: str
    query: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_count: int = Field(ge=0)
    limit: int = Field(gt=0)


class RetrievalBenchmarkCasesDiagnostics(InspectionModel):
    total_cases: int = Field(ge=0)
    evidence_case_count: int = Field(ge=0)
    empty_case_count: int = Field(ge=0)
    expected_chunk_ref_count: int = Field(ge=0)
    min_limit: int = Field(gt=0)
    max_limit: int = Field(gt=0)


class RetrievalBenchmarkDryRunResult(InspectionModel):
    source_work_id: str
    character_id: str
    embedding_model: str | None = None
    cases_source: Literal["generated", "explicit"] = "generated"
    will_create_run: bool = False
    cases_summary: RetrievalBenchmarkCasesDiagnostics
    cases: list[RetrievalBenchmarkCaseSummary] = Field(default_factory=list)


def prepare_ooc_benchmark_cases(
    *,
    case_suite: str = DEFAULT_BENCHMARK_CASE_SUITE,
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> tuple[BenchmarkCase, ...]:
    return cases if cases is not None else get_benchmark_cases(case_suite)


def dry_run_ooc_benchmark(
    session: Session,
    *,
    character_id: str,
    persona_version_id: str | None = None,
    case_suite: str = DEFAULT_BENCHMARK_CASE_SUITE,
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> OOCBenchmarkDryRunResult:
    character = CharacterRepository(session).require(character_id)
    persona = (
        PersonaVersionRepository(session).require(persona_version_id)
        if persona_version_id is not None
        else PersonaVersionRepository(session).latest_for_character(character.id)
    )
    if persona is None:
        raise ValueError(f"Character {character_id!r} has no persona version")
    if persona.character_id != character.id:
        raise ValueError(
            f"Persona version {persona.id!r} does not belong to character {character.id!r}"
        )

    benchmark_cases = prepare_ooc_benchmark_cases(case_suite=case_suite, cases=cases)
    return OOCBenchmarkDryRunResult(
        character_id=character.id,
        persona_version_id=persona.id,
        case_suite=case_suite if cases is None else None,
        cases_source="explicit" if cases is not None else "case_suite",
        cases_summary=_ooc_cases_summary(benchmark_cases),
        cases=[_ooc_case_summary(benchmark_case) for benchmark_case in benchmark_cases],
    )


def run_ooc_benchmark_workflow(
    session: Session,
    *,
    character_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    persona_version_id: str | None = None,
    test_suite: str = DEFAULT_OOC_TEST_SUITE,
    case_suite: str = DEFAULT_BENCHMARK_CASE_SUITE,
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> EvaluationRunDetail:
    benchmark_cases = prepare_ooc_benchmark_cases(case_suite=case_suite, cases=cases)
    result = run_ooc_benchmark(
        session,
        character_id=character_id,
        provider=provider,
        model_config=model_config,
        persona_version_id=persona_version_id,
        test_suite=test_suite,
        cases=benchmark_cases,
    )
    return get_evaluation_run_detail(session, result.run.id)


def get_ooc_benchmark_report(
    session: Session,
    run_id: str,
    *,
    failed_only: bool = False,
) -> EvaluationRunDetail:
    return get_evaluation_run_detail(session, run_id, failed_only=failed_only)


def prepare_retrieval_benchmark_cases(
    session: Session,
    *,
    character_id: str,
    cases: tuple[RetrievalBenchmarkCase, ...] | None = None,
    max_cases: int = 20,
    include_empty_case: bool = True,
) -> tuple[RetrievalBenchmarkCase, ...]:
    if cases is not None:
        return cases
    return build_default_retrieval_benchmark_cases(
        session,
        character_id=character_id,
        max_cases=max_cases,
        include_empty_case=include_empty_case,
    )


def dry_run_retrieval_benchmark(
    session: Session,
    *,
    character_id: str,
    cases: tuple[RetrievalBenchmarkCase, ...] | None = None,
    max_cases: int = 20,
    include_empty_case: bool = True,
    embedding_config: EmbeddingConfig | None = None,
) -> RetrievalBenchmarkDryRunResult:
    character = CharacterRepository(session).require(character_id)
    benchmark_cases = prepare_retrieval_benchmark_cases(
        session,
        character_id=character.id,
        cases=cases,
        max_cases=max_cases,
        include_empty_case=include_empty_case,
    )
    return RetrievalBenchmarkDryRunResult(
        source_work_id=character.source_work_id,
        character_id=character.id,
        embedding_model=embedding_config.model if embedding_config is not None else None,
        cases_source="explicit" if cases is not None else "generated",
        cases_summary=_retrieval_cases_summary(benchmark_cases),
        cases=[
            _retrieval_case_summary(benchmark_case)
            for benchmark_case in benchmark_cases
        ],
    )


def run_retrieval_benchmark_workflow(
    session: Session,
    *,
    character_id: str,
    provider: LLMProvider | None = None,
    embedding_config: EmbeddingConfig | None = None,
    test_suite: str = DEFAULT_RETRIEVAL_TEST_SUITE,
    cases: tuple[RetrievalBenchmarkCase, ...] | None = None,
    max_cases: int = 20,
    include_empty_case: bool = True,
) -> RetrievalEvaluationRunDetail:
    result = run_retrieval_benchmark(
        session,
        character_id=character_id,
        provider=provider,
        embedding_config=embedding_config,
        test_suite=test_suite,
        cases=cases,
        max_cases=max_cases,
        include_empty_case=include_empty_case,
    )
    return get_retrieval_evaluation_run_detail(session, result.run.id)


def get_retrieval_benchmark_report(
    session: Session,
    run_id: str,
    *,
    failed_only: bool = False,
    include_chunks: bool = True,
) -> RetrievalEvaluationRunDetail:
    return get_retrieval_evaluation_run_detail(
        session,
        run_id,
        failed_only=failed_only,
        include_chunks=include_chunks,
    )


def _ooc_case_summary(benchmark_case: BenchmarkCase) -> OOCBenchmarkCaseSummary:
    return OOCBenchmarkCaseSummary(
        id=benchmark_case.id,
        prompt=benchmark_case.prompt,
        interaction_mode=benchmark_case.interaction_mode,
        category=benchmark_case.category,
    )


def _ooc_cases_summary(
    cases: tuple[BenchmarkCase, ...],
) -> OOCBenchmarkCasesSummary:
    interaction_modes = sorted(
        {benchmark_case.interaction_mode for benchmark_case in cases},
        key=lambda mode: str(getattr(mode, "value", mode)),
    )
    mode_reports = []
    for interaction_mode in interaction_modes:
        total_cases = sum(
            1
            for benchmark_case in cases
            if benchmark_case.interaction_mode == interaction_mode
        )
        mode_reports.append(
            BenchmarkModeDiagnostics(
                interaction_mode=interaction_mode,
                total_cases=total_cases,
                passed_cases=0,
                failed_cases=0,
                pass_rate=0.0,
            )
        )
    return OOCBenchmarkCasesSummary(
        total_cases=len(cases),
        mode_reports=mode_reports,
    )


def _retrieval_case_summary(
    benchmark_case: RetrievalBenchmarkCase,
) -> RetrievalBenchmarkCaseSummary:
    return RetrievalBenchmarkCaseSummary(
        id=benchmark_case.id,
        query=benchmark_case.query,
        expected_chunk_ids=list(benchmark_case.expected_chunk_ids),
        expected_count=len(benchmark_case.expected_chunk_ids),
        limit=benchmark_case.limit,
    )


def _retrieval_cases_summary(
    cases: tuple[RetrievalBenchmarkCase, ...],
) -> RetrievalBenchmarkCasesDiagnostics:
    summary = summarize_retrieval_benchmark_cases(cases)
    return RetrievalBenchmarkCasesDiagnostics(
        total_cases=summary.total_cases,
        evidence_case_count=summary.evidence_case_count,
        empty_case_count=summary.empty_case_count,
        expected_chunk_ref_count=summary.expected_chunk_ref_count,
        min_limit=summary.min_limit,
        max_limit=summary.max_limit,
    )
