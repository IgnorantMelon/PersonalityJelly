from __future__ import annotations

import pytest
from pydantic import ValidationError

import personality_jelly.application.sources as source_application
from personality_jelly.application import (
    MAX_INLINE_SOURCE_CONTENT_CHARS,
    SOURCE_WORK_INGEST_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    LocalActorContext,
    SourceWorkIngestChunking,
    SourceWorkIngestRequest,
    build_idempotency_context,
    ingest_source_work_workflow,
)
from personality_jelly.domain import SourceWork
from personality_jelly.storage import (
    AuditEventRepository,
    IdempotencyRecordRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_inline_markdown_persists_source_chunks_audit_workflow_and_replay() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        request = _request(
            source_work_id="sw_inline",
            content="# Chapter One\n\nLin Shuang observed first.\n\nThen she acted.",
            metadata={"client_label": "batch10"},
        )
        idempotency = build_idempotency_context(
            workflow_type=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
            idempotency_key="source-retry-key",
            request_payload={
                "source_work_id": "sw_inline",
                "title": "Inline Source",
                "content": request.content,
            },
        )

        result = ingest_source_work_workflow(session, request, idempotency=idempotency)

        stored_source = SourceWorkRepository(session).require("sw_inline")
        stored_chunks = SourceChunkRepository(session).list_by_source_work("sw_inline")
        stored_audit = AuditEventRepository(session).require(result.audit_event.id)
        workflow_run = WorkflowRunRepository(session).require(result.workflow_id)
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(result.workflow_id)
        replay_records = IdempotencyRecordRepository(session).list_all()

    assert stored_source.title == "Inline Source"
    assert stored_source.author == "Author"
    assert stored_source.language == "zh-CN"
    assert stored_source.source_type == "markdown"
    assert [chunk.text for chunk in stored_chunks] == [
        "Lin Shuang observed first.",
        "Then she acted.",
    ]
    assert result.request_id == "req_source_ingest"
    assert result.workflow_id.startswith("wf_")
    assert result.workflow_type == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert result.status == "completed"
    assert result.ids.source_work_id == "sw_inline"
    assert result.ids.audit_event_id == result.audit_event.id
    assert result.ids.audit_event_ids == [result.audit_event.id]
    assert result.llm_trace_ids == []
    assert result.ids.llm_trace_ids == []
    assert result.source_work.id == "sw_inline"
    assert result.chunk_count == 2
    assert result.source_chunk_ids == [chunk.id for chunk in stored_chunks]
    assert result.first_chunk_id == stored_chunks[0].id
    assert result.last_chunk_id == stored_chunks[-1].id
    assert result.text_redacted is True
    assert result.source_preview_redacted is True

    assert stored_audit.operation == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert stored_audit.result == "succeeded"
    assert stored_audit.entity_type == "source_work"
    assert stored_audit.entity_id == "sw_inline"
    assert stored_audit.request_id == "req_source_ingest"
    assert stored_audit.workflow_id == result.workflow_id
    assert stored_audit.workflow_type == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert stored_audit.related_ids == {"source_work_id": "sw_inline"}
    assert stored_audit.after is not None
    assert stored_audit.after["source_work"]["title"] == "Inline Source"
    assert stored_audit.after["chunk_count"] == 2
    assert stored_audit.after["text_redacted"] is True
    assert "Lin Shuang observed first." not in str(stored_audit.after)
    assert "Then she acted." not in str(stored_audit.metadata)

    assert workflow_run.status == "completed"
    assert workflow_run.request_id == "req_source_ingest"
    assert workflow_run.workflow_type == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert workflow_run.persisted_ids["source_work_id"] == "sw_inline"
    assert workflow_run.persisted_ids["audit_event_id"] == result.audit_event.id
    assert (
        "Lin Shuang observed first."
        not in str(workflow_run.persisted_ids) + str(workflow_run.warnings)
    )
    assert {(link.entity_type, link.entity_id, link.relation) for link in workflow_links} == {
        ("source_work", "sw_inline", "created"),
        *(("source_chunk", chunk.id, "created") for chunk in stored_chunks),
        ("audit_event", result.audit_event.id, "audit"),
        ("idempotency_record", replay_records[0].id, "idempotency"),
    }

    assert len(replay_records) == 1
    replay = replay_records[0]
    assert replay.workflow_type == SOURCE_WORK_INGEST_WORKFLOW_TYPE
    assert replay.idempotency_key == "source-retry-key"
    assert replay.request_hash != request.content
    assert replay.response_status_code == 201
    assert replay.replay_payload["result"]["text_redacted"] is True
    assert replay.replay_payload["result"]["source_preview_redacted"] is True
    assert replay.related_ids["source_work_id"] == "sw_inline"
    assert replay.related_ids["source_chunk_ids"] == result.source_chunk_ids
    assert "Lin Shuang observed first." not in str(replay.replay_payload)


def test_inline_txt_is_accepted() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        result = ingest_source_work_workflow(
            session,
            _request(source_work_id="sw_txt", source_type="txt", content="A plain paragraph."),
        )

        stored_source = SourceWorkRepository(session).require("sw_txt")
        stored_chunks = SourceChunkRepository(session).list_by_source_work("sw_txt")

    assert stored_source.source_type == "txt"
    assert result.chunk_count == 1
    assert [chunk.text for chunk in stored_chunks] == ["A plain paragraph."]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"title": "   "}, "must not be blank"),
        ({"content": "   "}, "content must not be blank"),
        ({"source_type": "pdf"}, "source_type must be markdown or txt"),
        ({"content_encoding": "base64"}, "content_encoding must be omitted or utf-8"),
        ({"actor": None}, "local actor context is required"),
        (
            {"chunking": SourceWorkIngestChunking(max_paragraph_chars=100, min_paragraph_chars=101)},
            "must not exceed",
        ),
        ({"content": "x" * (MAX_INLINE_SOURCE_CONTENT_CHARS + 1)}, "at most"),
        (
            {"chunking": SourceWorkIngestChunking(min_paragraph_chars=20), "content": "short"},
            "zero source chunks",
        ),
        ({"metadata": {"path": "sample.md"}}, "forbidden source reference"),
        ({"metadata": {"label": "C:\\Users\\tester\\sample.md"}}, "local paths"),
        ({"metadata": {"source_url": "https://example.test/source.md"}}, "URLs"),
        ({"metadata": {"provider_config": {"model": "x"}}}, "forbidden"),
        ({"metadata": {"payload": "QUJD" * 30}}, "base64"),
    ],
)
def test_validation_failures_persist_nothing(updates, message: str) -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        with pytest.raises((ValueError, ValidationError), match=message):
            request = _request(**updates)
            ingest_source_work_workflow(session, request)

        assert SourceWorkRepository(session).list_all() == []
        assert SourceChunkRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []
        assert WorkflowRunRepository(session).list_all() == []
        assert WorkflowRunLinkRepository(session).list_all() == []
        assert IdempotencyRecordRepository(session).list_all() == []


def test_actor_metadata_path_like_value_is_rejected_before_persistence() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        request = _request(actor=_actor(metadata={"source_path": "C:\\tmp\\source.md"}))

        with pytest.raises(ValueError, match="forbidden source reference"):
            ingest_source_work_workflow(session, request)

        assert SourceWorkRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []
        assert WorkflowRunRepository(session).list_all() == []


def test_explicit_source_work_id_collision_raises_conflict_and_persists_nothing_new() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_existing", title="Existing", source_type="markdown")
        )
        session.commit()

        with pytest.raises(ConflictError, match="SourceWork 'sw_existing' already exists"):
            ingest_source_work_workflow(session, _request(source_work_id="sw_existing"))

        assert [source.id for source in SourceWorkRepository(session).list_all()] == [
            "sw_existing"
        ]
        assert SourceChunkRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []
        assert WorkflowRunRepository(session).list_all() == []


def test_forced_audit_failure_rolls_back_domain_workflow_links_and_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()

    def fail_audit_persistence(*args, **kwargs):
        raise RuntimeError("audit persistence failed")

    monkeypatch.setattr(source_application, "persist_audit_event", fail_audit_persistence)

    with session_factory() as session:
        idempotency = build_idempotency_context(
            workflow_type=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
            idempotency_key="rollback-key",
            request_payload={"source_work_id": "sw_rollback"},
        )

        with pytest.raises(RuntimeError, match="audit persistence failed"):
            ingest_source_work_workflow(
                session,
                _request(source_work_id="sw_rollback"),
                idempotency=idempotency,
            )

        assert SourceWorkRepository(session).get("sw_rollback") is None
        assert SourceChunkRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []
        assert WorkflowRunRepository(session).list_all() == []
        assert WorkflowRunLinkRepository(session).list_all() == []
        assert IdempotencyRecordRepository(session).list_all() == []


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _request(**updates) -> SourceWorkIngestRequest:
    payload = {
        "source_work_id": "sw_source",
        "title": "Inline Source",
        "author": "Author",
        "language": "zh-CN",
        "source_type": "markdown",
        "content": "First paragraph.\n\nSecond paragraph.",
        "content_encoding": "utf-8",
        "chunking": SourceWorkIngestChunking(max_paragraph_chars=500, min_paragraph_chars=1),
        "actor": _actor(),
        "correlation": CorrelationContext(request_id="req_source_ingest"),
        "metadata": {"client_label": "test"},
    }
    payload.update(updates)
    return SourceWorkIngestRequest(**payload)


def _actor(metadata: dict | None = None) -> LocalActorContext:
    return LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:test",
        actor_label="Local API test",
        user_id="user_001",
        operation_reason="ingest source for test",
        metadata=metadata or {"entrypoint": "test"},
    )
