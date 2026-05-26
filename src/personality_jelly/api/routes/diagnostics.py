from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session
from personality_jelly.application import (
    CriticReportDetail,
    EvaluationRunDetail,
    FailureCaseDetail,
    InspectionListResult,
    LLMTraceDetail,
    RetrievalEvaluationRunDetail,
    get_critic_report_detail,
    get_evaluation_run_detail,
    get_failure_case_detail,
    get_llm_trace_detail,
    get_retrieval_evaluation_run_detail,
    list_evaluation_runs,
    list_failure_cases,
    list_llm_traces,
    list_retrieval_evaluation_runs,
)

router = APIRouter(tags=["diagnostics"])

LimitQuery = Annotated[int | None, Query(ge=1)]


@router.get("/critic-reports/{critic_report_id}", response_model=CriticReportDetail)
def read_critic_report(
    critic_report_id: str,
    session: Session = Depends(get_session),
) -> CriticReportDetail:
    return get_critic_report_detail(session, critic_report_id)


@router.get("/failure-cases", response_model=InspectionListResult)
def read_failure_cases(
    conversation_id: str | None = None,
    category: str | None = None,
    limit: LimitQuery = None,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_failure_cases(
        session,
        conversation_id=conversation_id,
        category=category,
        limit=limit,
    )


@router.get("/failure-cases/{failure_case_id}", response_model=FailureCaseDetail)
def read_failure_case(
    failure_case_id: str,
    session: Session = Depends(get_session),
) -> FailureCaseDetail:
    return get_failure_case_detail(session, failure_case_id)


@router.get("/llm-traces", response_model=InspectionListResult)
def read_llm_traces(
    operation: str | None = None,
    schema_name: str | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
    with_errors: bool = False,
    limit: LimitQuery = None,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_llm_traces(
        session,
        operation=operation,
        schema_name=schema_name,
        provider_name=provider_name,
        model_name=model_name,
        with_errors=with_errors,
        limit=limit,
    )


@router.get("/llm-traces/{trace_id}", response_model=LLMTraceDetail)
def read_llm_trace(
    trace_id: str,
    session: Session = Depends(get_session),
) -> LLMTraceDetail:
    return get_llm_trace_detail(session, trace_id)


@router.get("/eval-runs", response_model=InspectionListResult)
def read_eval_runs(
    character_id: str | None = None,
    test_suite: str | None = None,
    limit: LimitQuery = None,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_evaluation_runs(
        session,
        character_id=character_id,
        test_suite=test_suite,
        limit=limit,
    )


@router.get("/eval-runs/{run_id}", response_model=EvaluationRunDetail)
def read_eval_run(
    run_id: str,
    failed_only: bool = False,
    session: Session = Depends(get_session),
) -> EvaluationRunDetail:
    return get_evaluation_run_detail(session, run_id, failed_only=failed_only)


@router.get("/retrieval-eval-runs", response_model=InspectionListResult)
def read_retrieval_eval_runs(
    character_id: str | None = None,
    source_work_id: str | None = None,
    test_suite: str | None = None,
    limit: LimitQuery = None,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_retrieval_evaluation_runs(
        session,
        character_id=character_id,
        source_work_id=source_work_id,
        test_suite=test_suite,
        limit=limit,
    )


@router.get("/retrieval-eval-runs/{run_id}", response_model=RetrievalEvaluationRunDetail)
def read_retrieval_eval_run(
    run_id: str,
    failed_only: bool = False,
    include_chunks: bool = True,
    session: Session = Depends(get_session),
) -> RetrievalEvaluationRunDetail:
    return get_retrieval_evaluation_run_detail(
        session,
        run_id,
        failed_only=failed_only,
        include_chunks=include_chunks,
    )
