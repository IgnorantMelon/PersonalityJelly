from __future__ import annotations

import pytest
from pydantic import ValidationError

from personality_jelly.application import (
    CorrelationContext,
    WorkflowRelatedIds,
    WorkflowStatus,
    WorkflowWarning,
    build_error_correlation,
    build_workflow_response,
    dump_error_correlation,
    fail_persisted_workflow,
    start_persisted_workflow,
    start_workflow,
)
from personality_jelly.storage import (
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_start_workflow_generates_transport_neutral_context() -> None:
    correlation = CorrelationContext(request_id=" req_client ")

    workflow = start_workflow(
        correlation,
        workflow_type=" conversation.create ",
    )

    assert workflow.request_id == "req_client"
    assert workflow.workflow_id.startswith("wf_")
    assert len(workflow.workflow_id) <= 128
    assert workflow.workflow_type == "conversation.create"
    assert workflow.status == "running"


def test_workflow_response_summary_includes_ids_and_warnings() -> None:
    workflow = start_workflow(
        CorrelationContext(request_id="req_client"),
        workflow_type="memory.review",
        workflow_id="wf_client",
    )

    response = build_workflow_response(
        workflow,
        status=WorkflowStatus.COMPLETED,
        ids=WorkflowRelatedIds(
            memory_id=" mem_001 ",
            audit_event_id=" audit_001 ",
            llm_trace_ids=[" llmraw_001 "],
        ),
        warnings=[
            WorkflowWarning(
                code="review_note",
                message="Manual review kept the memory as candidate.",
            )
        ],
    )

    assert response.model_dump(mode="json") == {
        "request_id": "req_client",
        "workflow_id": "wf_client",
        "workflow_type": "memory.review",
        "status": "completed",
        "ids": {
            "source_work_id": None,
            "character_id": None,
            "user_id": None,
            "conversation_id": None,
            "persona_version_id": None,
            "user_message_id": None,
            "assistant_message_id": None,
            "rejected_assistant_message_id": None,
            "context_package_id": None,
            "critic_report_id": None,
            "rejected_critic_report_id": None,
            "memory_id": "mem_001",
            "evaluation_run_id": None,
            "retrieval_evaluation_run_id": None,
            "audit_event_id": "audit_001",
            "failure_case_ids": [],
            "memory_ids": [],
            "evaluation_case_result_ids": [],
            "retrieval_evaluation_case_result_ids": [],
            "audit_event_ids": [],
            "llm_trace_ids": ["llmraw_001"],
        },
        "warnings": [
            {
                "code": "review_note",
                "message": "Manual review kept the memory as candidate.",
                "details": {},
            }
        ],
    }


def test_correlation_models_reject_blank_and_oversized_ids() -> None:
    with pytest.raises(ValidationError, match="request_id must not be blank"):
        CorrelationContext(request_id="  ")

    with pytest.raises(ValidationError, match="request_id must be at most 128 characters"):
        CorrelationContext(request_id="x" * 129)

    with pytest.raises(ValidationError, match="related id must not be blank"):
        WorkflowRelatedIds(memory_ids=["mem_001", "  "])


def test_error_correlation_dump_is_bounded_to_safe_correlation_fields() -> None:
    workflow = start_workflow(
        CorrelationContext(request_id="req_provider"),
        workflow_type="conversation.turn",
        workflow_id="wf_provider",
    )

    correlation = build_error_correlation(
        workflow,
        status=WorkflowStatus.PARTIAL,
        ids=WorkflowRelatedIds(
            conversation_id="conv_001",
            user_message_id="msg_user",
            context_package_id="ctx_001",
            llm_trace_ids=["llmraw_001"],
        ),
        failed_step="critic_evaluate",
    )

    assert dump_error_correlation(correlation) == {
        "request_id": "req_provider",
        "workflow_id": "wf_provider",
        "workflow_type": "conversation.turn",
        "status": "partial",
        "ids": {
            "conversation_id": "conv_001",
            "user_message_id": "msg_user",
            "context_package_id": "ctx_001",
            "llm_trace_ids": ["llmraw_001"],
        },
        "failed_step": "critic_evaluate",
    }


def test_persisted_workflow_can_be_marked_failed_with_safe_error_details() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        workflow = start_persisted_workflow(
            session,
            CorrelationContext(request_id="req_failed"),
            workflow_type="memory.archive",
            related_ids=WorkflowRelatedIds(memory_id="mem_001"),
        )
        failed = fail_persisted_workflow(
            session,
            workflow,
            error_code="invalid_status_transition",
            error_details={"reason": "memory is already archived"},
            failed_step="memory.archive",
            ids=WorkflowRelatedIds(memory_id="mem_001", memory_ids=["mem_001"]),
        )
        session.commit()

    with session_factory() as session:
        stored = WorkflowRunRepository(session).require(failed.workflow_id)

    assert failed.status == "failed"
    assert stored.status == "failed"
    assert stored.completed_at is not None
    assert stored.error_code == "invalid_status_transition"
    assert stored.error_details == {"reason": "memory is already archived"}
    assert stored.failed_step == "memory.archive"
    assert stored.persisted_ids == {"memory_id": "mem_001", "memory_ids": ["mem_001"]}
