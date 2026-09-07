from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_session
from personality_jelly.api.redaction import redact_payload
from personality_jelly.application import (
    AuditEventDetail,
    CriticReportDetail,
    DEFAULT_INSPECTION_LIMIT,
    EvaluationRunDetail,
    FailureCaseDetail,
    InspectionListResult,
    LLMTraceDetail,
    RetrievalEvaluationRunDetail,
    WorkflowRunDetail,
    get_audit_event_detail,
    get_critic_report_detail,
    get_evaluation_run_detail,
    get_failure_case_detail,
    get_llm_trace_detail,
    get_retrieval_evaluation_run_detail,
    get_workflow_run_detail,
    list_audit_events,
    list_evaluation_runs,
    list_failure_cases,
    list_llm_traces,
    list_retrieval_evaluation_runs,
    list_workflow_runs,
)

router = APIRouter(tags=["diagnostics"])

LimitQuery = Annotated[int | None, Query(ge=1)]
InspectionLimitQuery = Annotated[int, Query(ge=1, le=200)]


def _redacted_model(
    model: Any,
    model_type: type[AuditEventDetail] | type[WorkflowRunDetail],
) -> AuditEventDetail | WorkflowRunDetail:
    return model_type.model_validate(redact_payload(model))


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


@router.get("/audit-events", response_model=InspectionListResult)
def read_audit_events(
    request_id: str | None = None,
    workflow_id: str | None = None,
    workflow_type: str | None = None,
    operation: str | None = None,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    character_id: str | None = None,
    conversation_id: str | None = None,
    limit: InspectionLimitQuery = DEFAULT_INSPECTION_LIMIT,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_audit_events(
        session,
        request_id=request_id,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        operation=operation,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        limit=limit,
    )


@router.get("/audit-events/{audit_event_id}", response_model=AuditEventDetail)
def read_audit_event(
    audit_event_id: str,
    session: Session = Depends(get_session),
) -> AuditEventDetail:
    return _redacted_model(get_audit_event_detail(session, audit_event_id), AuditEventDetail)


@router.get("/workflow-runs", response_model=InspectionListResult)
def read_workflow_runs(
    request_id: str | None = None,
    workflow_id: str | None = None,
    workflow_type: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    character_id: str | None = None,
    conversation_id: str | None = None,
    limit: InspectionLimitQuery = DEFAULT_INSPECTION_LIMIT,
    session: Session = Depends(get_session),
) -> InspectionListResult:
    return list_workflow_runs(
        session,
        request_id=request_id,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        status=status,
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        limit=limit,
    )


@router.get("/workflow-runs/{workflow_id}", response_model=WorkflowRunDetail)
def read_workflow_run(
    workflow_id: str,
    session: Session = Depends(get_session),
) -> WorkflowRunDetail:
    return _redacted_model(get_workflow_run_detail(session, workflow_id), WorkflowRunDetail)


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
