from __future__ import annotations

import pytest
from pydantic import ValidationError

import personality_jelly.application.characters as character_application
from personality_jelly.application import (
    CHARACTER_CREATE_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    LocalActorContext,
    CharacterCreateRequest,
    build_idempotency_context,
    create_character_workflow,
)
from personality_jelly.domain import SourceWork
from personality_jelly.storage import (
    AuditEventRepository,
    CharacterRepository,
    IdempotencyRecordRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_character_creation_persists_character_audit_workflow_links_and_replay() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_work(session)
        idempotency = build_idempotency_context(
            workflow_type=CHARACTER_CREATE_WORKFLOW_TYPE,
            idempotency_key="character-create-key",
            request_payload={
                "source_work_id": "sw_source",
                "canonical_name": "Lin Shuang",
                "aliases": ["A Shuang"],
            },
        )

        result = create_character_workflow(
            session,
            _request(
                character_id="char_lin",
                canonical_name="  Lin   Shuang ",
                aliases=["A Shuang", " Lin Shuang ", "", "A Shuang"],
                metadata={"client_label": "batch10"},
            ),
            idempotency=idempotency,
        )

        stored_character = CharacterRepository(session).require("char_lin")
        stored_audit = AuditEventRepository(session).require(result.audit_event.id)
        workflow_run = WorkflowRunRepository(session).require(result.workflow_id)
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(result.workflow_id)
        replay_records = IdempotencyRecordRepository(session).list_all()

    assert stored_character.canonical_name == "Lin Shuang"
    assert stored_character.aliases == ["A Shuang"]
    assert result.request_id == "req_character_create"
    assert result.workflow_type == CHARACTER_CREATE_WORKFLOW_TYPE
    assert result.status == "completed"
    assert result.ids.source_work_id == "sw_source"
    assert result.ids.character_id == "char_lin"
    assert result.ids.audit_event_id == result.audit_event.id
    assert result.ids.audit_event_ids == [result.audit_event.id]
    assert result.ids.llm_trace_ids == []
    assert result.character.character_id == "char_lin"
    assert result.character.source_work_id == "sw_source"
    assert result.character.canonical_name == "Lin Shuang"
    assert result.character.aliases == ["A Shuang"]
    assert result.character.latest_persona_version_id is None

    assert stored_audit.operation == CHARACTER_CREATE_WORKFLOW_TYPE
    assert stored_audit.result == "succeeded"
    assert stored_audit.entity_type == "character"
    assert stored_audit.entity_id == "char_lin"
    assert stored_audit.related_ids == {
        "source_work_id": "sw_source",
        "character_id": "char_lin",
    }
    assert stored_audit.after == result.character.model_dump(mode="json")
    assert stored_audit.metadata["source_work_id"] == "sw_source"
    assert stored_audit.metadata["character_id"] == "char_lin"
    assert stored_audit.metadata["alias_count"] == 1
    assert stored_audit.metadata["client_metadata"] == {"client_label": "batch10"}
    assert stored_audit.metadata["source_text_redacted"] is True
    assert "First source paragraph" not in str(stored_audit.metadata)

    assert workflow_run.status == "completed"
    assert workflow_run.workflow_type == CHARACTER_CREATE_WORKFLOW_TYPE
    assert workflow_run.persisted_ids["source_work_id"] == "sw_source"
    assert workflow_run.persisted_ids["character_id"] == "char_lin"
    assert workflow_run.persisted_ids["audit_event_id"] == result.audit_event.id
    assert {(link.entity_type, link.entity_id, link.relation) for link in workflow_links} == {
        ("source_work", "sw_source", "input"),
        ("character", "char_lin", "created"),
        ("audit_event", result.audit_event.id, "audit"),
        ("idempotency_record", replay_records[0].id, "idempotency"),
    }

    assert len(replay_records) == 1
    replay = replay_records[0]
    assert replay.workflow_type == CHARACTER_CREATE_WORKFLOW_TYPE
    assert replay.idempotency_key == "character-create-key"
    assert replay.response_status_code == 201
    assert replay.related_ids["source_work_id"] == "sw_source"
    assert replay.related_ids["character_id"] == "char_lin"
    assert replay.replay_payload["result"]["character"]["latest_persona_version_id"] is None
    assert replay.replay_payload["result"]["audit_event"]["reason"] == "[redacted:reason]"


def test_missing_source_work_raises_lookup_and_persists_nothing() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        with pytest.raises(LookupError):
            create_character_workflow(session, _request(source_work_id="missing_source"))

        _assert_counts(session, characters=0, audits=0, workflows=0, links=0)


def test_blank_canonical_name_persists_nothing() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_work(session)

        with pytest.raises(ValidationError, match="must not be blank"):
            create_character_workflow(session, _request(canonical_name="   "))

        _assert_counts(session, characters=0, audits=0, workflows=0, links=0)


def test_duplicate_name_in_same_source_work_raises_conflict_and_persists_nothing_new() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_work(session)
        create_character_workflow(
            session,
            _request(character_id="char_existing", canonical_name="Lin Shuang"),
        )

        with pytest.raises(ConflictError, match="already exists"):
            create_character_workflow(
                session,
                _request(character_id="char_duplicate", canonical_name="  Lin   Shuang "),
            )

        assert [character.id for character in CharacterRepository(session).list_all()] == [
            "char_existing"
        ]
        assert len(AuditEventRepository(session).list_all()) == 1
        assert len(WorkflowRunRepository(session).list_all()) == 1


def test_explicit_character_id_collision_raises_conflict_and_persists_nothing_new() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_work(session)
        create_character_workflow(
            session,
            _request(character_id="char_existing", canonical_name="Lin Shuang"),
        )

        with pytest.raises(ConflictError, match="already exists"):
            create_character_workflow(
                session,
                _request(character_id="char_existing", canonical_name="Other Name"),
            )

        assert [character.id for character in CharacterRepository(session).list_all()] == [
            "char_existing"
        ]
        assert len(AuditEventRepository(session).list_all()) == 1
        assert len(WorkflowRunRepository(session).list_all()) == 1


def test_forbidden_metadata_and_actor_metadata_persist_nothing() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_work(session)

        with pytest.raises(ValidationError, match="forbidden source reference"):
            create_character_workflow(
                session,
                _request(metadata={"provider_config": {"model": "x"}}),
            )

        with pytest.raises(ValueError, match="forbidden source reference"):
            create_character_workflow(
                session,
                _request(actor=_actor(metadata={"source_path": r"C:\tmp\source.md"})),
            )

        _assert_counts(session, characters=0, audits=0, workflows=0, links=0)


def test_audit_failure_rolls_back_character_workflow_links_and_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()

    def fail_audit_persistence(*args, **kwargs):
        raise RuntimeError("audit persistence failed")

    monkeypatch.setattr(character_application, "persist_audit_event", fail_audit_persistence)

    with session_factory() as session:
        _seed_source_work(session)
        idempotency = build_idempotency_context(
            workflow_type=CHARACTER_CREATE_WORKFLOW_TYPE,
            idempotency_key="rollback-key",
            request_payload={"character_id": "char_rollback"},
        )

        with pytest.raises(RuntimeError, match="audit persistence failed"):
            create_character_workflow(
                session,
                _request(character_id="char_rollback"),
                idempotency=idempotency,
            )

        assert CharacterRepository(session).get("char_rollback") is None
        _assert_counts(
            session,
            characters=0,
            audits=0,
            workflows=0,
            links=0,
            idempotency_records=0,
        )


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_source_work(session, source_work_id: str = "sw_source") -> None:
    SourceWorkRepository(session).add(
        SourceWork(
            id=source_work_id,
            title="Inline Source",
            author="Author",
            source_type="markdown",
        )
    )


def _request(**updates) -> CharacterCreateRequest:
    payload = {
        "source_work_id": "sw_source",
        "canonical_name": "Lin Shuang",
        "aliases": ["A Shuang"],
        "character_id": "char_lin",
        "actor": _actor(),
        "correlation": CorrelationContext(request_id="req_character_create"),
        "metadata": {"client_label": "test"},
    }
    payload.update(updates)
    return CharacterCreateRequest(**payload)


def _actor(metadata: dict | None = None) -> LocalActorContext:
    return LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:test",
        actor_label="Local API test",
        user_id="user_001",
        operation_reason="create character for test",
        metadata=metadata or {"entrypoint": "test"},
    )


def _assert_counts(
    session,
    *,
    characters: int,
    audits: int,
    workflows: int,
    links: int,
    idempotency_records: int = 0,
) -> None:
    assert len(CharacterRepository(session).list_all()) == characters
    assert len(AuditEventRepository(session).list_all()) == audits
    assert len(WorkflowRunRepository(session).list_all()) == workflows
    assert len(WorkflowRunLinkRepository(session).list_all()) == links
    assert len(IdempotencyRecordRepository(session).list_all()) == idempotency_records
