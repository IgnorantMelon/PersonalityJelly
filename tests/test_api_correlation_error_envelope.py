from __future__ import annotations

import pytest

from personality_jelly.api.errors import build_error_envelope
from personality_jelly.api.schemas import (
    WriteResponseEnvelope,
    resolve_write_request_correlation,
)
from personality_jelly.application import (
    CorrelationContext,
    NormalizedError,
    PartialPersistenceError,
    WorkflowRelatedIds,
    WorkflowStatus,
    WorkflowWarning,
    build_error_correlation,
    build_partial_persistence_details,
    normalize_error,
    start_workflow,
)


def test_resolve_write_request_correlation_generates_bounded_request_id() -> None:
    correlation = resolve_write_request_correlation()

    assert correlation.request_id.startswith("req_")
    assert len(correlation.request_id) <= 128
    assert correlation.to_application_context() == CorrelationContext(
        request_id=correlation.request_id
    )


def test_resolve_write_request_correlation_accepts_matching_header_and_body() -> None:
    correlation = resolve_write_request_correlation(
        header_request_id=" req_client ",
        body_request_id="req_client",
    )

    assert correlation.request_id == "req_client"


@pytest.mark.parametrize(
    ("header_request_id", "body_request_id", "message"),
    [
        ("   ", None, "X-Request-ID must not be blank"),
        ("x" * 129, None, "X-Request-ID must be at most 128 characters"),
        ("req_header", "req_body", "X-Request-ID and body request_id must match"),
        (None, "   ", "body request_id must not be blank"),
    ],
)
def test_resolve_write_request_correlation_rejects_invalid_request_ids(
    header_request_id: object | None,
    body_request_id: object | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_write_request_correlation(
            header_request_id=header_request_id,
            body_request_id=body_request_id,
        )


def test_write_response_envelope_serializes_correlation_and_result() -> None:
    workflow = start_workflow(
        CorrelationContext(request_id="req_client"),
        workflow_type="memory.archive",
        workflow_id="wf_archive",
        related_ids=WorkflowRelatedIds(memory_id="mem_001"),
    )

    envelope = WriteResponseEnvelope.from_workflow(
        workflow,
        status=WorkflowStatus.COMPLETED,
        ids=WorkflowRelatedIds(memory_id="mem_001", audit_event_id="audit_001"),
        warnings=[
            WorkflowWarning(
                code="payload_only_audit",
                message="Audit event is returned in the response only.",
            )
        ],
        result={"memory": {"id": "mem_001", "status": "archived"}},
    )

    assert envelope.model_dump(mode="json") == {
        "request_id": "req_client",
        "workflow_id": "wf_archive",
        "workflow_type": "memory.archive",
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
            "llm_trace_ids": [],
        },
        "warnings": [
            {
                "code": "payload_only_audit",
                "message": "Audit event is returned in the response only.",
                "details": {},
            }
        ],
        "result": {"memory": {"id": "mem_001", "status": "archived"}},
    }


def test_error_envelope_can_include_sanitized_correlation_without_reusing_trace_id() -> None:
    workflow = start_workflow(
        CorrelationContext(request_id="req_provider"),
        workflow_type="conversation.turn",
        workflow_id="wf_provider",
    )
    correlation = build_error_correlation(
        workflow,
        status=WorkflowStatus.FAILED,
        ids=WorkflowRelatedIds(
            conversation_id="conv_001",
            context_package_id="ctx_001",
            llm_trace_ids=["llmraw_001"],
        ),
        failed_step="critic_evaluate",
    )

    envelope = build_error_envelope(
        NormalizedError(
            code="provider_validation_error",
            message="Provider output failed schema validation",
            details={"retry_hint": "retry_after_idempotency_support"},
        ),
        correlation=correlation,
        trace_id="llmraw_001",
    )
    payload = envelope.model_dump(mode="json")

    assert payload == {
        "error": {
            "code": "provider_validation_error",
            "message": "Provider output failed schema validation",
            "details": {
                "retry_hint": "retry_after_idempotency_support",
                "correlation": {
                    "request_id": "req_provider",
                    "workflow_id": "wf_provider",
                    "workflow_type": "conversation.turn",
                    "status": "failed",
                    "ids": {
                        "conversation_id": "conv_001",
                        "context_package_id": "ctx_001",
                        "llm_trace_ids": ["llmraw_001"],
                    },
                    "failed_step": "critic_evaluate",
                },
            },
            "trace_id": "llmraw_001",
        }
    }


def test_partial_persistence_error_envelope_keeps_correlation_under_details() -> None:
    workflow = start_workflow(
        CorrelationContext(request_id="req_partial"),
        workflow_type="conversation.turn",
        workflow_id="wf_partial",
    )
    ids = WorkflowRelatedIds(
        conversation_id="conv_001",
        assistant_message_id="msg_assistant",
        llm_trace_ids=["llmraw_guard"],
        audit_event_ids=["audit_partial"],
    )
    correlation = build_error_correlation(
        workflow,
        status=WorkflowStatus.PARTIAL,
        ids=ids,
        failed_step="memory_guard",
    )
    details = build_partial_persistence_details(
        failed_step="memory_guard",
        error_code="guard_provider_failed",
        workflow_id="wf_partial",
        persisted_ids={
            "conversation_id": "conv_001",
            "assistant_message_id": "msg_assistant",
            "assembled_prompt": "raw prompt must not leak",
        },
        llm_trace_ids=["llmraw_guard"],
        audit_event_ids=["audit_partial"],
        retry_hint="retry_with_same_idempotency_key",
        details={
            "raw_provider_response": {"text": "provider payload"},
            "local_path": r"C:\Users\figna\trace.json",
        },
    )

    envelope = build_error_envelope(
        normalize_error(PartialPersistenceError(details=details)),
        correlation=correlation,
        trace_id="llmraw_guard",
    )
    payload = envelope.model_dump(mode="json")

    assert payload["error"]["code"] == "partial_persistence"
    assert payload["error"]["trace_id"] == "llmraw_guard"
    assert payload["error"]["details"]["workflow_id"] == "wf_partial"
    assert payload["error"]["details"]["persisted_ids"]["assistant_message_id"] == (
        "msg_assistant"
    )
    assert payload["error"]["details"]["persisted_ids"]["assembled_prompt"] == (
        "[redacted:prompt]"
    )
    assert payload["error"]["details"]["llm_trace_ids"] == ["llmraw_guard"]
    assert payload["error"]["details"]["audit_event_ids"] == ["audit_partial"]
    assert payload["error"]["details"]["retry_hint"] == "retry_with_same_idempotency_key"
    assert payload["error"]["details"]["details"]["raw_provider_response"] == (
        "[redacted:provider_payload]"
    )
    assert payload["error"]["details"]["details"]["local_path"] == "[redacted:path]"
    assert payload["error"]["details"]["correlation"] == {
        "request_id": "req_partial",
        "workflow_id": "wf_partial",
        "workflow_type": "conversation.turn",
        "status": "partial",
        "ids": {
            "conversation_id": "conv_001",
            "assistant_message_id": "msg_assistant",
            "audit_event_ids": ["audit_partial"],
            "llm_trace_ids": ["llmraw_guard"],
        },
        "failed_step": "memory_guard",
    }
    assert "raw prompt" not in str(payload)
    assert r"C:\Users" not in str(payload)
