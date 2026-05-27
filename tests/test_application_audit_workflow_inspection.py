from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from personality_jelly.application import (
    get_audit_event_detail,
    get_workflow_run_detail,
    list_audit_events,
    list_workflow_runs,
)
from personality_jelly.domain import AuditEvent, WorkflowRun, WorkflowRunLink
from personality_jelly.storage import (
    AuditEventRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


NOW = datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(minutes=5)


def test_audit_event_inspection_lists_with_default_limit_ordering_and_filters() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_audit_events(session)

        result = list_audit_events(session)
        limited = list_audit_events(session, limit=1)

        assert result.limit == 50
        assert result.total_count == 3
        assert [item.id for item in result.items] == ["audit_002", "audit_001", "audit_000"]
        assert [item.id for item in limited.items] == ["audit_002"]

        filter_cases = [
            ({"request_id": "req_001"}, ["audit_001"]),
            ({"workflow_id": "wf_001"}, ["audit_001"]),
            ({"workflow_type": "memory.review"}, ["audit_001"]),
            ({"operation": "memory.review"}, ["audit_001"]),
            ({"actor_id": "api-local:reviewer"}, ["audit_001"]),
            ({"entity_type": "memory"}, ["audit_001"]),
            ({"entity_id": "mem_001"}, ["audit_001"]),
            ({"status": "succeeded"}, ["audit_001"]),
            ({"user_id": "user_001"}, ["audit_001"]),
            ({"character_id": "char_001"}, ["audit_001"]),
            ({"conversation_id": "conv_001"}, ["audit_001"]),
        ]
        for filters, expected_ids in filter_cases:
            filtered = list_audit_events(session, **filters)
            assert [item.id for item in filtered.items] == expected_ids


def test_audit_event_inspection_detail_and_limit_validation() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_audit_events(session)

        detail = get_audit_event_detail(session, "audit_001")

        assert detail.id == "audit_001"
        assert detail.reason == "User supplied audit reason."
        assert detail.before["content"] == "Raw before memory content."
        assert detail.metadata["api_key"] == "sk-audit-secret"

        with pytest.raises(LookupError):
            get_audit_event_detail(session, "missing_audit")
        with pytest.raises(ValueError, match="greater than 0"):
            list_audit_events(session, limit=0)
        with pytest.raises(ValueError, match="at most 200"):
            list_audit_events(session, limit=201)


def test_workflow_run_inspection_lists_with_default_limit_ordering_and_filters() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_workflow_runs(session)

        result = list_workflow_runs(session)
        limited = list_workflow_runs(session, limit=1)

        assert result.limit == 50
        assert result.total_count == 3
        assert [item.workflow_id for item in result.items] == ["wf_002", "wf_001", "wf_000"]
        assert [item.workflow_id for item in limited.items] == ["wf_002"]

        filter_cases = [
            ({"request_id": "req_001"}, ["wf_001"]),
            ({"workflow_id": "wf_001"}, ["wf_001"]),
            ({"workflow_type": "memory.review"}, ["wf_001"]),
            ({"status": "completed"}, ["wf_001"]),
            ({"user_id": "user_001"}, ["wf_001"]),
            ({"character_id": "char_001"}, ["wf_001"]),
            ({"conversation_id": "conv_001"}, ["wf_001"]),
            (
                {
                    "user_id": "user_001",
                    "character_id": "char_001",
                    "conversation_id": "conv_001",
                },
                ["wf_001"],
            ),
        ]
        for filters, expected_ids in filter_cases:
            filtered = list_workflow_runs(session, **filters)
            assert [item.workflow_id for item in filtered.items] == expected_ids


def test_workflow_run_inspection_detail_links_and_limit_validation() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_workflow_runs(session)

        detail = get_workflow_run_detail(session, "wf_002")

        assert detail.workflow_id == "wf_002"
        assert detail.error_details["assembled_prompt"] == "Raw workflow prompt."
        assert detail.warnings[0]["reason"] == "Raw workflow warning reason."
        assert [link.entity_type for link in detail.links] == ["character", "user"]

        with pytest.raises(LookupError):
            get_workflow_run_detail(session, "missing_workflow")
        with pytest.raises(ValueError, match="greater than 0"):
            list_workflow_runs(session, limit=0)
        with pytest.raises(ValueError, match="at most 200"):
            list_workflow_runs(session, limit=201)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_audit_events(session) -> None:
    repository = AuditEventRepository(session)
    repository.add(
        AuditEvent(
            id="audit_001",
            created_at=NOW,
            operation="memory.review",
            result="succeeded",
            actor_type="api_user",
            actor_id="api-local:reviewer",
            entity_type="memory",
            entity_id="mem_001",
            reason="User supplied audit reason.",
            request_id="req_001",
            workflow_id="wf_001",
            workflow_type="memory.review",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            memory_id="mem_001",
            related_ids={"memory_id": "mem_001"},
            before={
                "id": "mem_001",
                "scope": "user_memory",
                "status": "candidate",
                "importance": 0.7,
                "content": "Raw before memory content.",
                "reason": "Raw before memory reason.",
            },
            after={
                "id": "mem_001",
                "scope": "user_memory",
                "status": "accepted",
                "importance": 0.7,
                "content": "Raw after memory content.",
                "reason": "Raw after memory reason.",
            },
            metadata={"api_key": "sk-audit-secret"},
        )
    )
    repository.add(
        AuditEvent(
            id="audit_002",
            created_at=NOW,
            operation="memory.edit",
            result="failed",
            actor_type="api_user",
            actor_id="api-local:other",
            entity_type="conversation",
            entity_id="conv_002",
            reason="Other audit reason.",
            request_id="req_002",
            workflow_id="wf_002",
            workflow_type="memory.edit",
            user_id="user_002",
            character_id="char_002",
            conversation_id="conv_002",
        )
    )
    repository.add(
        AuditEvent(
            id="audit_000",
            created_at=EARLIER,
            operation="conversation.create",
            result="skipped",
            actor_type="api_user",
            actor_id="api-local:old",
            entity_type="conversation",
            entity_id="conv_000",
            reason="Older audit reason.",
            request_id="req_000",
            workflow_id="wf_000",
            workflow_type="conversation.create",
            user_id="user_000",
            character_id="char_000",
            conversation_id="conv_000",
        )
    )


def _seed_workflow_runs(session) -> None:
    run_repository = WorkflowRunRepository(session)
    link_repository = WorkflowRunLinkRepository(session)
    run_repository.add(
        WorkflowRun(
            workflow_id="wf_001",
            request_id="req_001",
            workflow_type="memory.review",
            status="completed",
            started_at=NOW,
            completed_at=NOW,
            persisted_ids={"memory_id": "mem_001"},
        )
    )
    run_repository.add(
        WorkflowRun(
            workflow_id="wf_002",
            request_id="req_002",
            workflow_type="memory.edit",
            status="failed",
            started_at=NOW,
            completed_at=NOW,
            error_code="provider_failure",
            error_details={
                "assembled_prompt": "Raw workflow prompt.",
                "provider_response_payload": {"body": "Raw provider payload."},
            },
            failed_step="provider_call",
            warnings=[
                {
                    "code": "partial",
                    "reason": "Raw workflow warning reason.",
                }
            ],
            persisted_ids={"memory_id": "mem_002"},
        )
    )
    run_repository.add(
        WorkflowRun(
            workflow_id="wf_000",
            request_id="req_000",
            workflow_type="conversation.create",
            status="running",
            started_at=EARLIER,
        )
    )
    for link in [
        WorkflowRunLink(
            id="wflink_001_user",
            workflow_id="wf_001",
            entity_type="user",
            entity_id="user_001",
            relation="owner",
            created_at=NOW,
        ),
        WorkflowRunLink(
            id="wflink_001_character",
            workflow_id="wf_001",
            entity_type="character",
            entity_id="char_001",
            relation="subject",
            created_at=NOW,
        ),
        WorkflowRunLink(
            id="wflink_001_conversation",
            workflow_id="wf_001",
            entity_type="conversation",
            entity_id="conv_001",
            relation="created",
            created_at=NOW,
        ),
        WorkflowRunLink(
            id="wflink_002_user",
            workflow_id="wf_002",
            entity_type="user",
            entity_id="user_002",
            relation="owner",
            created_at=NOW,
        ),
        WorkflowRunLink(
            id="wflink_002_character",
            workflow_id="wf_002",
            entity_type="character",
            entity_id="char_002",
            relation="subject",
            created_at=NOW,
        ),
    ]:
        link_repository.add(link)
