from __future__ import annotations

import json

import pytest

from personality_jelly.application import (
    AuditActorType,
    AuditEntity,
    AuditRelatedIds,
    AuditResult,
    CorrelationContext,
    CriticFailureError,
    GuardFailureError,
    LocalActorContext,
    PartialPersistenceError,
    ProviderFailureError,
    ProviderValidationFailureError,
    RetryableConflictError,
    WorkflowFailureCode,
    WorkflowLinkSpec,
    WorkflowRelatedIds,
    build_partial_persistence_details,
    build_provider_failure_details,
    build_workflow_failure_audit_event,
    build_idempotency_context,
    normalize_error,
    partial_persisted_workflow,
    start_persisted_workflow,
    store_idempotency_replay,
)
from personality_jelly.application.audit import persist_audit_event
from personality_jelly.domain import WorkflowRun
from personality_jelly.storage import (
    AuditEventRepository,
    IdempotencyRecordRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_provider_failure_details_are_normalized_and_redacted() -> None:
    details = build_provider_failure_details(
        error_family=WorkflowFailureCode.PROVIDER_VALIDATION_ERROR,
        error_code="schema_validation_failed",
        failed_step=" critic_evaluate ",
        workflow_id=" wf_provider ",
        persisted_ids={
            "conversation_id": "conv_001",
            "memory_content": "User likes midnight drafting.",
            "assembled_prompt": "system prompt and full source chunk",
        },
        llm_trace_ids=[" llmraw_001 "],
        audit_event_ids=[" audit_001 "],
        retry_hint="retry_with_same_workflow_id_after_idempotency_support",
        details={
            "api_key": "sk-live-secret-12345",
            "raw_provider_response": {"text": "provider payload"},
            "local_path": r"C:\Users\figna\prompt.txt",
            "stack_trace": "Traceback (most recent call last)\nsecret",
            "source_chunk_text": "Full source chunk should not leak.",
            "validation_errors": [{"loc": ["content"], "msg": "bad raw output"}],
            "message": r"failed opening C:\Projects\PersonalityJelly\secret.txt",
        },
    )

    normalized = normalize_error(
        ProviderValidationFailureError(
            r"provider output invalid at C:\Users\figna\trace.json",
            details=details,
        )
    )
    payload = normalized.details
    serialized = _serialized({"message": normalized.message, "details": payload})

    assert normalized.code == "provider_validation_error"
    assert payload["error_family"] == "provider_validation_error"
    assert payload["error_code"] == "schema_validation_failed"
    assert payload["failed_step"] == "critic_evaluate"
    assert payload["workflow_id"] == "wf_provider"
    assert payload["persisted_ids"]["conversation_id"] == "conv_001"
    assert payload["persisted_ids"]["memory_content"] == "[redacted:user_text]"
    assert payload["persisted_ids"]["assembled_prompt"] == "[redacted:prompt]"
    assert payload["llm_trace_ids"] == ["llmraw_001"]
    assert payload["audit_event_ids"] == ["audit_001"]
    assert payload["details"]["api_key"] == "[redacted:secret]"
    assert payload["details"]["raw_provider_response"] == "[redacted:provider_payload]"
    assert payload["details"]["validation_errors"] == "[redacted:trace_payload]"
    assert payload["details"]["message"] == "failed opening [redacted:path]"
    assert "sk-live-secret" not in serialized
    assert "C:\\Users" not in serialized
    assert "Full source chunk" not in serialized
    assert "Traceback" not in serialized


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ProviderFailureError(details={"error_code": "timeout"}), "provider_failure"),
        (
            ProviderValidationFailureError(details={"error_code": "schema_mismatch"}),
            "provider_validation_error",
        ),
        (
            PartialPersistenceError(
                details=build_partial_persistence_details(
                    failed_step="memory_guard",
                    error_code="guard_provider_failed",
                )
            ),
            "partial_persistence",
        ),
        (
            RetryableConflictError(details={"error_code": "workflow_in_progress"}),
            "retryable_conflict",
        ),
        (CriticFailureError(details={"error_code": "critic_required"}), "critic_failure"),
        (GuardFailureError(details={"error_code": "guard_required"}), "guard_failure"),
    ],
)
def test_normalize_error_maps_provider_workflow_failure_codes(error: Exception, code: str) -> None:
    normalized = normalize_error(error)

    assert normalized.code == code
    assert normalized.details["error_family"] == code
    assert normalized.details["error_code"]


def test_partial_persisted_workflow_records_safe_details_links_and_audit() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        workflow = start_persisted_workflow(
            session,
            CorrelationContext(request_id="req_partial"),
            workflow_type="conversation.turn",
            workflow_id="wf_partial",
            related_ids=WorkflowRelatedIds(conversation_id="conv_001"),
        )
        partial_details = build_partial_persistence_details(
            failed_step="memory_guard",
            error_code="guard_provider_failed",
            workflow_id=workflow.workflow_id,
            persisted_ids={
                "conversation_id": "conv_001",
                "assistant_message_id": "msg_assistant",
                "assembled_prompt": "raw prompt should not leak",
            },
            llm_trace_ids=["llmraw_guard"],
            audit_event_ids=["audit_partial"],
            retry_hint="retry_with_same_idempotency_key",
            details={
                "raw_provider_payload": {"memory_content": "User memory"},
                "source_chunks": ["full source text"],
                "path": r"C:\Users\figna\provider.log",
            },
        )
        normalized = normalize_error(PartialPersistenceError(details=partial_details))
        ids = WorkflowRelatedIds(
            conversation_id="conv_001",
            assistant_message_id="msg_assistant",
            llm_trace_ids=["llmraw_guard"],
            audit_event_ids=["audit_partial"],
        )
        partial = partial_persisted_workflow(
            session,
            workflow,
            error_code=normalized.code,
            error_details=normalized.details,
            failed_step="memory_guard",
            ids=ids,
            links=[
                WorkflowLinkSpec(
                    entity_type="message",
                    entity_id="msg_assistant",
                    relation="created",
                ),
                WorkflowLinkSpec(
                    entity_type="llm_trace",
                    entity_id="llmraw_guard",
                    relation="trace",
                ),
            ],
        )
        audit_event = build_workflow_failure_audit_event(
            actor=LocalActorContext(
                actor_type=AuditActorType.SYSTEM,
                actor_id="provider-workflow",
                operation_reason="Provider workflow failed after durable records.",
            ),
            operation="conversation.turn",
            entity=AuditEntity(entity_type="conversation", entity_id="conv_001"),
            related_ids=AuditRelatedIds(
                conversation_id="conv_001",
                llm_trace_id="llmraw_guard",
            ),
            correlation=partial,
            result=AuditResult.PARTIAL,
            failure_details=normalized.details,
        )
        persist_audit_event(session, audit_event)
        session.commit()

    with session_factory() as session:
        stored = WorkflowRunRepository(session).require("wf_partial")
        links = WorkflowRunLinkRepository(session).list_by_workflow("wf_partial")
        audit = AuditEventRepository(session).require(audit_event.id)

    assert partial.status == "partial"
    assert stored.status == "partial"
    assert stored.error_code == "partial_persistence"
    assert stored.failed_step == "memory_guard"
    assert stored.persisted_ids == {
        "conversation_id": "conv_001",
        "assistant_message_id": "msg_assistant",
        "audit_event_ids": ["audit_partial"],
        "llm_trace_ids": ["llmraw_guard"],
    }
    assert stored.error_details["persisted_ids"]["assembled_prompt"] == "[redacted:prompt]"
    assert stored.error_details["details"]["raw_provider_payload"] == (
        "[redacted:provider_payload]"
    )
    assert stored.error_details["details"]["source_chunks"] == "[redacted:source_text]"
    assert stored.error_details["details"]["path"] == "[redacted:path]"
    assert sorted((link.entity_type, link.entity_id, link.relation) for link in links) == [
        ("llm_trace", "llmraw_guard", "trace"),
        ("message", "msg_assistant", "created"),
    ]
    assert audit.result == "partial"
    assert audit.workflow_id == "wf_partial"
    assert audit.metadata["failure"]["error_family"] == "partial_persistence"
    assert "raw prompt" not in _serialized(stored.error_details)
    assert "full source text" not in _serialized(audit.metadata)
    assert "C:\\Users" not in _serialized(audit.metadata)


def test_failure_contract_can_be_stored_for_idempotency_replay() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_replay_partial",
                request_id="req_original",
                workflow_type="conversation.turn",
                status="partial",
            )
        )
        context = build_idempotency_context(
            workflow_type="conversation.turn",
            idempotency_key="turn-provider-key",
            request_payload={"conversation_id": "conv_001", "content": "Hello"},
        )
        details = build_partial_persistence_details(
            failed_step="critic_evaluate",
            error_code="critic_provider_failed",
            workflow_id="wf_replay_partial",
            persisted_ids={"conversation_id": "conv_001", "content": "raw user text"},
            llm_trace_ids=["llmraw_critic"],
            retry_hint="replay_partial_outcome_without_provider_call",
            details={"provider_response": "raw body", "api_key": "sk-hidden-secret"},
        )
        normalized = normalize_error(PartialPersistenceError(details=details))
        replay_payload = {
            "error": {
                "code": normalized.code,
                "message": normalized.message,
                "details": normalized.details,
                "trace_id": "llmraw_critic",
            }
        }
        store_idempotency_replay(
            session,
            context,
            request_id="req_original",
            workflow_id="wf_replay_partial",
            status="partial",
            response_status_code=500,
            replay_payload=replay_payload,
            related_ids=WorkflowRelatedIds(
                conversation_id="conv_001",
                llm_trace_ids=["llmraw_critic"],
            ),
            error_code=normalized.code,
            error_details=normalized.details,
        )
        session.commit()

    with session_factory() as session:
        record = IdempotencyRecordRepository(session).list_all()[0]

    assert record.status == "partial"
    assert record.response_status_code == 500
    assert record.error_code == "partial_persistence"
    assert record.error_details["retry_hint"] == "replay_partial_outcome_without_provider_call"
    assert record.error_details["persisted_ids"]["content"] == "[redacted:user_text]"
    assert record.replay_payload["error"]["trace_id"] == "llmraw_critic"
    assert record.related_ids == {
        "conversation_id": "conv_001",
        "llm_trace_ids": ["llmraw_critic"],
    }
    assert "raw user text" not in _serialized(record.model_dump(mode="json"))
    assert "sk-hidden-secret" not in _serialized(record.model_dump(mode="json"))


def _serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
