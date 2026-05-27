from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.api.redaction import (
    REDACTED_PATH,
    REDACTED_PROMPT,
    REDACTED_PROVIDER_PAYLOAD,
    REDACTED_REASON,
    REDACTED_SECRET,
    REDACTED_STACK_TRACE,
    REDACTED_USER_TEXT,
)
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
from personality_jelly.domain import AuditEvent, WorkflowRun, WorkflowRunLink
from personality_jelly.storage import (
    AuditEventRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
)
from personality_jelly.storage.database import session_scope


NOW = datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(minutes=5)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_audit_event_route_lists_default_page_ordering_and_filters(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/audit-events")

        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 50
        assert body["total_count"] == 3
        assert [item["id"] for item in body["items"]] == [
            "audit_002",
            "audit_001",
            "audit_000",
        ]
        assert "User supplied audit reason." not in response.text
        assert "Raw before memory content." not in response.text

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
            ({"limit": 1}, ["audit_002"]),
        ]
        for params, expected_ids in filter_cases:
            filtered = client.get("/audit-events", params=params)
            assert filtered.status_code == 200
            assert [item["id"] for item in filtered.json()["items"]] == expected_ids


def test_audit_event_detail_route_redacts_sensitive_payloads(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/audit-events/audit_001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "audit_001"
    assert body["reason"] == REDACTED_REASON
    assert body["before"]["content"] == REDACTED_USER_TEXT
    assert body["before"]["reason"] == REDACTED_REASON
    assert body["after"]["content"] == REDACTED_USER_TEXT
    assert body["after"]["reason"] == REDACTED_REASON
    assert body["metadata"]["api_key"] == REDACTED_SECRET
    assert body["metadata"]["assembled_prompt"] == REDACTED_PROMPT
    assert body["metadata"]["provider_response_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert body["metadata"]["local_path"] == REDACTED_PATH
    assert body["metadata"]["stack_trace"] == REDACTED_STACK_TRACE
    assert body["metadata"]["nested"]["message"] == f"opened {REDACTED_PATH}"
    assert "User supplied audit reason." not in response.text
    assert "Raw before memory content." not in response.text
    assert "Raw after memory content." not in response.text
    assert "sk-audit-secret" not in response.text
    assert "Raw assembled audit prompt." not in response.text
    assert "Raw audit provider payload." not in response.text
    assert "C:\\Users\\figna" not in response.text
    assert "Traceback" not in response.text


def test_workflow_run_route_lists_default_page_ordering_and_filters(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/workflow-runs")

        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 50
        assert body["total_count"] == 3
        assert [item["workflow_id"] for item in body["items"]] == [
            "wf_002",
            "wf_001",
            "wf_000",
        ]
        assert "Raw workflow prompt." not in response.text
        assert "Raw workflow warning reason." not in response.text

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
            ({"limit": 1}, ["wf_002"]),
        ]
        for params, expected_ids in filter_cases:
            filtered = client.get("/workflow-runs", params=params)
            assert filtered.status_code == 200
            assert [item["workflow_id"] for item in filtered.json()["items"]] == expected_ids


def test_workflow_run_detail_route_returns_links_and_redacts_payloads(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/workflow-runs/wf_002")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "wf_002"
    assert body["status"] == "failed"
    assert [link["entity_type"] for link in body["links"]] == ["character", "user"]
    assert body["error_details"]["assembled_prompt"] == REDACTED_PROMPT
    assert body["error_details"]["provider_response_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert body["error_details"]["local_path"] == REDACTED_PATH
    assert body["error_details"]["stack_trace"] == REDACTED_STACK_TRACE
    assert body["warnings"][0]["reason"] == REDACTED_REASON
    assert body["warnings"][0]["provider_request_payload"] == REDACTED_PROVIDER_PAYLOAD
    assert body["warnings"][0]["message"] == f"opened {REDACTED_PATH}"
    assert "Raw workflow prompt." not in response.text
    assert "Raw workflow provider payload." not in response.text
    assert "Raw workflow warning reason." not in response.text
    assert "Raw warning provider payload." not in response.text
    assert "C:\\Users\\figna" not in response.text
    assert "Traceback" not in response.text


def test_audit_and_workflow_detail_routes_return_not_found_envelopes(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        responses = [
            client.get("/audit-events/missing_audit"),
            client.get("/workflow-runs/missing_workflow"),
        ]

    for response in responses:
        body = response.json()
        assert response.status_code == 404
        assert body["error"]["code"] == "not_found"
        assert "missing" in body["error"]["message"]
        assert body["error"]["trace_id"] is None


def test_audit_and_workflow_list_routes_reject_invalid_limits(tmp_path) -> None:
    app = _seed_api_app(tmp_path)

    with TestClient(app) as client:
        responses = [
            client.get("/audit-events", params={"limit": 0}),
            client.get("/audit-events", params={"limit": 201}),
            client.get("/workflow-runs", params={"limit": 0}),
            client.get("/workflow-runs", params={"limit": 201}),
        ]

    for response in responses:
        body = response.json()
        assert response.status_code == 422
        assert body["error"]["code"] == "validation_error"
        assert body["error"]["details"]["errors"][0]["loc"] == ["query", "limit"]


def _seed_api_app(tmp_path):
    resources = create_database_resources(f"sqlite:///{tmp_path / 'api-audit-workflow.db'}")
    with session_scope(resources.session_factory) as session:
        _seed_records(session)
    return create_app(settings=_settings(), database_resources=resources)


def _seed_records(session) -> None:
    _seed_audit_events(session)
    _seed_workflow_runs(session)


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
            metadata={
                "api_key": "sk-audit-secret",
                "assembled_prompt": "Raw assembled audit prompt.",
                "provider_response_payload": {"body": "Raw audit provider payload."},
                "local_path": "C:\\Users\\figna\\private\\audit.json",
                "stack_trace": (
                    "Traceback (most recent call last):\n"
                    "  File \"C:\\Users\\figna\\private\\audit.py\""
                ),
                "nested": {"message": "opened C:\\Users\\figna\\private\\audit.json"},
            },
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
                "provider_response_payload": {"body": "Raw workflow provider payload."},
                "local_path": "C:\\Users\\figna\\private\\workflow.json",
                "stack_trace": (
                    "Traceback (most recent call last):\n"
                    "  File \"C:\\Users\\figna\\private\\workflow.py\""
                ),
            },
            failed_step="provider_call",
            warnings=[
                {
                    "code": "partial",
                    "reason": "Raw workflow warning reason.",
                    "provider_request_payload": {"body": "Raw warning provider payload."},
                    "message": "opened C:\\Users\\figna\\private\\warning.json",
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
