from __future__ import annotations

import pytest

import personality_jelly.application.conversations as conversation_application
from personality_jelly.application import (
    CONVERSATION_CREATE_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    LocalActorContext,
    create_conversation_workflow,
)
from personality_jelly.domain import (
    Character,
    Conversation,
    InteractionMode,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    AuditEventRepository,
    CharacterRepository,
    ConversationRepository,
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_create_conversation_workflow_creates_conversation_with_actor_correlation_and_audit() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        session.commit()

        result = create_conversation_workflow(
            session,
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_created",
            actor_context=_actor(),
            correlation_context=CorrelationContext(request_id="req_create"),
        )

        stored = ConversationRepository(session).require("conv_created")
        stored_audit = AuditEventRepository(session).require(result.audit_event.id)
        messages = MessageRepository(session).list_by_conversation("conv_created")
        traces = LLMRawOutputRepository(session).list_recent()

    assert result.request_id == "req_create"
    assert result.workflow_id.startswith("wf_")
    assert result.workflow_type == CONVERSATION_CREATE_WORKFLOW_TYPE
    assert result.status == "completed"
    assert result.ids.conversation_id == "conv_created"
    assert result.ids.user_id == "user_001"
    assert result.ids.character_id == "char_001"
    assert result.ids.persona_version_id == "pv_latest"
    assert result.ids.audit_event_id == result.audit_event.id
    assert result.ids.audit_event_ids == [result.audit_event.id]
    assert result.conversation.conversation_id == "conv_created"
    assert result.conversation.current_mode == "reality_chat"
    assert stored.persona_version_id == "pv_latest"
    assert messages == []
    assert traces == []

    audit = result.audit_event
    assert audit.persistence == "payload_only"
    assert audit.operation == "conversation.create"
    assert audit.entity.entity_id == "conv_created"
    assert audit.related_ids.user_id == "user_001"
    assert audit.related_ids.character_id == "char_001"
    assert audit.related_ids.persona_version_id == "pv_latest"
    assert audit.metadata["request_id"] == "req_create"
    assert audit.metadata["workflow_id"] == result.workflow_id
    assert audit.metadata["workflow_status"] == "completed"
    assert audit.metadata["result"] == "succeeded"
    assert stored_audit.operation == "conversation.create"
    assert stored_audit.result == "succeeded"
    assert stored_audit.entity_type == "conversation"
    assert stored_audit.entity_id == "conv_created"
    assert stored_audit.request_id == "req_create"
    assert stored_audit.workflow_id == result.workflow_id
    assert stored_audit.workflow_type == "conversation.create"
    assert stored_audit.user_id == "user_001"
    assert stored_audit.character_id == "char_001"
    assert stored_audit.conversation_id == "conv_created"
    assert stored_audit.after is not None
    assert stored_audit.after["conversation_id"] == "conv_created"


def test_create_conversation_workflow_accepts_explicit_persona_and_mode() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        session.commit()

        result = create_conversation_workflow(
            session,
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_001",
            interaction_mode=InteractionMode.META_DISCUSSION,
            actor_context=_actor(),
            correlation_context=CorrelationContext(request_id="req_explicit"),
        )

    assert result.conversation.persona_version_id == "pv_001"
    assert result.conversation.current_mode == "meta_discussion"


@pytest.mark.parametrize(
    ("user_id", "character_id", "persona_version_id", "message"),
    [
        ("missing_user", "char_001", None, "UserORM 'missing_user' was not found"),
        ("user_001", "missing_char", None, "CharacterORM 'missing_char' was not found"),
        (
            "user_001",
            "char_001",
            "missing_persona",
            "PersonaVersionORM 'missing_persona' was not found",
        ),
    ],
)
def test_create_conversation_workflow_rejects_missing_required_ids(
    user_id: str,
    character_id: str,
    persona_version_id: str | None,
    message: str,
) -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        session.commit()

        with pytest.raises(LookupError, match=message):
            create_conversation_workflow(
                session,
                user_id=user_id,
                character_id=character_id,
                persona_version_id=persona_version_id,
                actor_context=_actor(user_id=user_id),
                correlation_context=CorrelationContext(request_id="req_missing"),
            )

        assert ConversationRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []


def test_create_conversation_workflow_rejects_persona_from_another_character() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session, include_other_character=True)
        session.commit()

        with pytest.raises(ValueError, match="does not belong to character"):
            create_conversation_workflow(
                session,
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_other",
                actor_context=_actor(),
                correlation_context=CorrelationContext(request_id="req_bad_persona"),
            )

        assert ConversationRepository(session).list_all() == []
        assert AuditEventRepository(session).list_all() == []


def test_create_conversation_workflow_requires_actor_user_to_match_domain_user() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        session.commit()

        with pytest.raises(ValueError, match="local actor context user_id must match user_id"):
            create_conversation_workflow(
                session,
                user_id="user_001",
                character_id="char_001",
                actor_context=_actor(user_id="user_other"),
                correlation_context=CorrelationContext(request_id="req_actor_mismatch"),
            )

        assert ConversationRepository(session).list_all() == []


def test_create_conversation_workflow_maps_explicit_id_collision_to_conflict() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        ConversationRepository(session).add(
            Conversation(
                id="conv_existing",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
            )
        )
        session.commit()

        with pytest.raises(ConflictError, match="Conversation 'conv_existing' already exists"):
            create_conversation_workflow(
                session,
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_existing",
                actor_context=_actor(),
                correlation_context=CorrelationContext(request_id="req_conflict"),
            )

        assert [conversation.id for conversation in ConversationRepository(session).list_all()] == [
            "conv_existing"
        ]
        assert AuditEventRepository(session).list_all() == []


def test_create_conversation_workflow_rolls_back_when_audit_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()

    def fail_audit_persistence(*args, **kwargs):
        raise RuntimeError("audit persistence failed")

    monkeypatch.setattr(
        conversation_application,
        "persist_audit_event",
        fail_audit_persistence,
    )

    with session_factory() as session:
        _seed_conversation_prerequisites(session)
        session.commit()

        with pytest.raises(RuntimeError, match="audit persistence failed"):
            create_conversation_workflow(
                session,
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_rollback",
                actor_context=_actor(),
                correlation_context=CorrelationContext(request_id="req_audit_fail"),
            )

        assert ConversationRepository(session).get("conv_rollback") is None
        assert AuditEventRepository(session).list_all() == []


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_conversation_prerequisites(
    session,
    *,
    include_other_character: bool = False,
) -> None:
    SourceWorkRepository(session).add(
        SourceWork(id="sw_001", title="Novel", source_type="markdown")
    )
    CharacterRepository(session).add(
        Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
        )
    )
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="pv_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="Careful observer.",
        )
    )
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="pv_latest",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=2,
            core_self="Careful observer, latest.",
        )
    )
    UserRepository(session).add(User(id="user_001", display_name="demo-user"))

    if include_other_character:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_002", title="Other Novel", source_type="markdown")
        )
        CharacterRepository(session).add(
            Character(
                id="char_other",
                source_work_id="sw_002",
                canonical_name="Other",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_other",
                character_id="char_other",
                source_work_id="sw_002",
                version_number=1,
                core_self="Other persona.",
            )
        )


def _actor(*, user_id: str = "user_001") -> LocalActorContext:
    return LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:test",
        actor_label="Local API test",
        user_id=user_id,
        metadata={"entrypoint": "test"},
    )
