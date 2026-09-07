from __future__ import annotations

import pytest

from personality_jelly.application import (
    ConflictError,
    WorkflowRelatedIds,
    build_idempotency_context,
    load_idempotency_replay,
    store_idempotency_replay,
)
from personality_jelly.domain import WorkflowRun
from personality_jelly.storage import (
    IdempotencyRecordRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_idempotency_helpers_store_replay_payload_and_conflict_on_hash_mismatch() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_replay",
                request_id="req_original",
                workflow_type="memory.edit",
                status="completed",
            )
        )
        context = build_idempotency_context(
            workflow_type="memory.edit",
            idempotency_key="retry-key",
            request_payload={
                "memory_id": "mem_001",
                "content": "User likes night writing.",
            },
        )
        store_idempotency_replay(
            session,
            context,
            request_id="req_original",
            workflow_id="wf_replay",
            status="completed",
            response_status_code=200,
            replay_payload={
                "request_id": "req_original",
                "workflow_id": "wf_replay",
                "result": {"memory": {"content": "[redacted:user_text]"}},
            },
            related_ids=WorkflowRelatedIds(memory_id="mem_001"),
        )
        session.commit()

    with session_factory() as session:
        context = build_idempotency_context(
            workflow_type="memory.edit",
            idempotency_key="retry-key",
            request_payload={
                "memory_id": "mem_001",
                "content": "User likes night writing.",
            },
        )
        replay = load_idempotency_replay(session, context)
        conflict_context = build_idempotency_context(
            workflow_type="memory.edit",
            idempotency_key="retry-key",
            request_payload={
                "memory_id": "mem_001",
                "content": "User likes sunrise drafting.",
            },
        )

        with pytest.raises(ConflictError) as exc_info:
            load_idempotency_replay(session, conflict_context)

        record = IdempotencyRecordRepository(session).find_by_scope(
            workflow_type="memory.edit",
            idempotency_key="retry-key",
        )

    assert replay is not None
    assert replay.response_status_code == 200
    assert replay.replay_payload["result"]["memory"]["content"] == "[redacted:user_text]"
    assert record is not None
    assert record.request_hash != "User likes night writing."
    assert "User likes sunrise drafting." not in str(exc_info.value.details)
    assert exc_info.value.details["conflict"] == "request_hash_mismatch"
