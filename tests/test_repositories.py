from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from personality_jelly.domain import (
    AuditEvent,
    Character,
    Conversation,
    ContextPackage,
    CriticReport,
    EvaluationStatus,
    FailureCase,
    IdempotencyRecord,
    InteractionMode,
    LLMRawOutput,
    Memory,
    MemoryScope,
    MemoryStatus,
    Message,
    MessageRole,
    PersonaVersion,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRun,
    SourceChunkEmbedding,
    SourceWork,
    User,
    WorkflowRun,
    WorkflowRunLink,
)
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.ingestion import chunk_source_text
from personality_jelly.storage import (
    AuditEventRepository,
    CharacterRepository,
    ConversationRepository,
    ContextPackageRepository,
    CriticReportRepository,
    FailureCaseRepository,
    IdempotencyRecordRepository,
    LLMRawOutputRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    RetrievalEvaluationCaseResultRepository,
    RetrievalEvaluationRunRepository,
    SourceChunkEmbeddingRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


NOW = datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc)


def test_audit_event_repository_roundtrips_and_lists_recent_filters() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = AuditEventRepository(session)
        repository.add(
            AuditEvent(
                id="audit_001",
                created_at=NOW,
                operation="conversation.create",
                result="succeeded",
                actor_type="api_user",
                actor_id="api-local:test",
                entity_type="conversation",
                entity_id="conv_001",
                reason="Create conversation.",
                request_id="req_001",
                workflow_id="wf_001",
                workflow_type="conversation.create",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                related_ids={
                    "user_id": "user_001",
                    "character_id": "char_001",
                    "conversation_id": "conv_001",
                },
                before=None,
                after={"conversation_id": "conv_001"},
                metadata={"result": "succeeded"},
            )
        )
        repository.add(
            AuditEvent(
                id="audit_002",
                created_at=NOW,
                operation="memory.review",
                result="succeeded",
                actor_type="api_user",
                actor_id="api-local:test",
                entity_type="memory",
                entity_id="mem_001",
                reason="Review memory.",
                request_id="req_002",
                workflow_id="wf_002",
                workflow_type="memory.review",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                memory_id="mem_001",
                related_ids={
                    "user_id": "user_001",
                    "character_id": "char_001",
                    "conversation_id": "conv_001",
                    "memory_id": "mem_001",
                },
                before={"status": "candidate"},
                after={"status": "accepted"},
                metadata={"result": "succeeded", "decision": "accept"},
            )
        )
        session.commit()

    with session_factory() as session:
        repository = AuditEventRepository(session)
        stored = repository.require("audit_002")
        recent = repository.list_recent(limit=1)
        by_operation = repository.list_recent(operation="conversation.create")
        by_memory = repository.list_recent(memory_id="mem_001")

    assert stored.operation == "memory.review"
    assert stored.result == "succeeded"
    assert stored.entity_type == "memory"
    assert stored.memory_id == "mem_001"
    assert stored.related_ids["memory_id"] == "mem_001"
    assert stored.before == {"status": "candidate"}
    assert stored.after == {"status": "accepted"}
    assert stored.metadata["decision"] == "accept"
    assert [event.id for event in recent] == ["audit_002"]
    assert [event.id for event in by_operation] == ["audit_001"]
    assert [event.id for event in by_memory] == ["audit_002"]


def test_audit_event_repository_is_append_only_by_primary_key() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    event = AuditEvent(
        id="audit_001",
        created_at=NOW,
        operation="memory.edit",
        result="succeeded",
        actor_type="api_user",
        actor_id="api-local:test",
        entity_type="memory",
        entity_id="mem_001",
        reason="Edit memory.",
        user_id="user_001",
        character_id="char_001",
        memory_id="mem_001",
    )

    with session_factory() as session:
        repository = AuditEventRepository(session)
        repository.add(event)
        with pytest.raises(IntegrityError):
            repository.add(event)
        session.rollback()


def test_repository_roundtrip_for_source_character_conversation_and_memory() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_work = SourceWork(
            id="sw_001",
            title="测试作品",
            source_type="markdown",
        )
        SourceWorkRepository(session).add(source_work)

        chunks = chunk_source_text("sw_001", "# 第一章\n\n她站在窗前。\n\n她听见钟声。")
        SourceChunkRepository(session).add_many(chunks)
        SourceChunkEmbeddingRepository(session).add_many(
            [
                SourceChunkEmbedding(
                    id="chunkemb_001",
                    source_chunk_id=chunks[0].id,
                    embedding_model="fake-embedding",
                    embedding=[0.9, 0.1],
                )
            ]
        )

        character = Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="她",
            aliases=["主角"],
        )
        CharacterRepository(session).add(character)

        persona = PersonaVersion(
            id="pv_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="她谨慎而敏锐。",
            speech_rules=["简洁"],
            forbidden_rules=["不能改写原作经历"],
        )
        PersonaVersionRepository(session).add(persona)

        user = User(id="user_001", display_name="测试用户")
        UserRepository(session).add(user)

        conversation = Conversation(
            id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="pv_001",
            current_mode=InteractionMode.REALITY_CHAT,
        )
        ConversationRepository(session).add(conversation)

        user_message = Message(
            id="msg_001",
            conversation_id="conv_001",
            role=MessageRole.USER,
            content="我今天很累。",
        )
        MessageRepository(session).add(user_message)

        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            conversation_id="conv_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="用户说过自己今天很累。",
            importance=0.5,
            reason="用户直接陈述了当前状态。",
        )
        MemoryRepository(session).add(memory)
        session.commit()

    with session_factory() as session:
        assert SourceWorkRepository(session).require("sw_001").title == "测试作品"
        stored_chunks = SourceChunkRepository(session).list_by_source_work("sw_001")
        assert len(stored_chunks) == 2
        stored_embeddings = SourceChunkEmbeddingRepository(session).list_for_chunks(
            [chunk.id for chunk in stored_chunks],
            embedding_model="fake-embedding",
        )
        assert stored_embeddings[0].embedding == [0.9, 0.1]
        assert CharacterRepository(session).list_by_source_work("sw_001")[0].aliases == ["主角"]
        assert PersonaVersionRepository(session).latest_for_character("char_001").id == "pv_001"
        conversations = ConversationRepository(session).list_for_user_character(
            "user_001",
            "char_001",
        )
        assert len(conversations) == 1
        assert ConversationRepository(session).list_recent(limit=1)[0].id == "conv_001"
        assert MessageRepository(session).list_by_conversation("conv_001")[0].content == "我今天很累。"
        assert (
            MemoryRepository(session)
            .list_for_user_character(
                "user_001",
                "char_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
            )[0]
            .content
            == "用户说过自己今天很累。"
        )


def test_repositories_find_reusable_cli_records() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(
                id="sw_001",
                title="测试作品",
                source_type="markdown",
            )
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="林霜",
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                character_id="char_001",
                source_work_id="sw_001",
                version_number=1,
                core_self="林霜谨慎敏锐。",
            )
        )
        UserRepository(session).add(User(id="user_001", display_name="demo-user"))
        ConversationRepository(session).add(
            Conversation(
                id="conv_001",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
                current_mode=InteractionMode.REALITY_CHAT,
            )
        )
        session.commit()

    with session_factory() as session:
        source_work = SourceWorkRepository(session).find_by_title("测试作品")
        character = CharacterRepository(session).find_by_source_work_and_name(
            "sw_001",
            "林霜",
        )
        user = UserRepository(session).find_by_display_name("demo-user")
        conversation = ConversationRepository(session).latest_for_user_character(
            "user_001",
            "char_001",
        )

    assert source_work.id == "sw_001"
    assert character.id == "char_001"
    assert user.id == "user_001"
    assert conversation.id == "conv_001"


def test_memory_repository_updates_content_and_status() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.ACCEPTED,
            content="用户喜欢清晨写作。",
            importance=0.7,
            reason="原始记录。",
        )
        repository = MemoryRepository(session)
        repository.add(memory)
        repository.update_content(
            "mem_001",
            content="用户喜欢夜里写作。",
            reason="用户修正了记忆。",
        )
        repository.update_status("mem_001", status=MemoryStatus.ARCHIVED)
        session.commit()

    with session_factory() as session:
        updated = MemoryRepository(session).require("mem_001")

    assert updated.content == "用户喜欢夜里写作。"
    assert updated.reason == "用户修正了记忆。"
    assert updated.status == "archived"


def test_memory_repository_reviews_candidate_memory() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        memory = Memory(
            id="mem_001",
            user_id="user_001",
            character_id="char_001",
            scope=MemoryScope.USER_MEMORY,
            status=MemoryStatus.CANDIDATE,
            content="用户喜欢夜里写作。",
            importance=0.7,
            reason="semantic guard unavailable; queued for review",
        )
        reviewed = MemoryRepository(session).add(memory)
        reviewed = MemoryRepository(session).review_candidate(
            reviewed.id,
            status=MemoryStatus.ACCEPTED,
            reason="用户明确确认这是稳定偏好。",
        )
        session.commit()

    with session_factory() as session:
        stored = MemoryRepository(session).require("mem_001")

    assert reviewed.status == "accepted"
    assert stored.status == "accepted"
    assert "Review decision accepted" in stored.reason
    assert "用户明确确认这是稳定偏好。" in stored.reason


def test_failure_case_repository_lists_recent_and_by_conversation() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Failure Work", source_type="markdown")
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
        UserRepository(session).add(User(id="user_001", display_name="tester"))
        ConversationRepository(session).add(
            Conversation(
                id="conv_001",
                user_id="user_001",
                character_id="char_001",
                persona_version_id="pv_001",
                current_mode=InteractionMode.REALITY_CHAT,
            )
        )
        ContextPackageRepository(session).add(
            ContextPackage(
                id="ctx_001",
                conversation_id="conv_001",
                interaction_mode=InteractionMode.REALITY_CHAT,
                persona_version_id="pv_001",
                assembled_prompt="Prompt",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_user_001",
                conversation_id="conv_001",
                role=MessageRole.USER,
                content="Who are you?",
            )
        )
        MessageRepository(session).add(
            Message(
                id="msg_assistant_001",
                conversation_id="conv_001",
                role=MessageRole.ASSISTANT,
                content="I am a generic assistant.",
                context_package_id="ctx_001",
            )
        )
        CriticReportRepository(session).add(
            CriticReport(
                id="cr_001",
                message_id="msg_assistant_001",
                ooc_risk="high",
                fact_risk="low",
                memory_risk="low",
                mode_risk="low",
                reasons=["Assistant broke character."],
                suggested_action="retry",
            )
        )
        FailureCaseRepository(session).add(
            FailureCase(
                id="fail_001",
                conversation_id="conv_001",
                user_message_id="msg_user_001",
                assistant_message_id="msg_assistant_001",
                context_package_id="ctx_001",
                critic_report_id="cr_001",
                category="retry",
                reason="Assistant broke character.",
                notes="Captured during retry.",
            )
        )
        session.commit()

    with session_factory() as session:
        repository = FailureCaseRepository(session)
        stored = repository.require("fail_001")
        recent = repository.list_recent(category="retry")
        by_conversation = repository.list_by_conversation("conv_001")

    assert stored.assistant_message_id == "msg_assistant_001"
    assert recent[0].id == "fail_001"
    assert by_conversation[0].reason == "Assistant broke character."


def test_llm_raw_output_repository_roundtrips_structured_trace() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        trace = LLMRawOutput(
            id="llmraw_001",
            operation="runtime.mode.classify_interaction_mode",
            schema_name="InteractionModeClassification",
            model_name="fake-mode",
            provider_name="mode-fake",
            request_id="req_trace",
            workflow_id="wf_trace",
            workflow_step="mode_classification",
            related_ids={"conversation_id": "conv_001"},
            response_schema={"title": "InteractionModeClassification"},
            raw_output='{"mode": "roleplay_scene"}',
            parsed_output={"mode": "roleplay_scene", "confidence": 0.9},
            validation_errors=[],
        )
        LLMRawOutputRepository(session).add(trace)
        session.commit()

    with session_factory() as session:
        repository = LLMRawOutputRepository(session)
        stored = repository.require("llmraw_001")
        traces = repository.list_by_operation("runtime.mode.classify_interaction_mode", limit=1)

    assert stored.provider_name == "mode-fake"
    assert stored.request_id == "req_trace"
    assert stored.workflow_id == "wf_trace"
    assert stored.workflow_step == "mode_classification"
    assert stored.related_ids == {"conversation_id": "conv_001"}
    assert stored.response_schema["title"] == "InteractionModeClassification"
    assert stored.parsed_output["mode"] == "roleplay_scene"
    assert traces[0].id == "llmraw_001"


def test_llm_trace_recorder_preserves_default_correlation_context() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_bound",
                request_id="req_bound",
                workflow_type="conversation.turn",
                status="running",
            )
        )
        recorder = RepositoryLLMTraceRecorder(
            LLMRawOutputRepository(session),
            request_id="req_bound",
            workflow_id="wf_bound",
            workflow_step="memory_guard",
            related_ids={"memory_id": "mem_001"},
        )
        trace = recorder.record(
            operation="memory.guard.semantic_decision",
            schema_name="MemoryGuardDecision",
            provider_name="guard-fake",
            model_name="fake-guard",
            response_schema={"title": "MemoryGuardDecision"},
            raw_output='{"decision": "allow"}',
            parsed_output={"decision": "allow"},
            validation_errors=[],
        )
        session.commit()

    with session_factory() as session:
        stored = LLMRawOutputRepository(session).require(trace.id)
        trace_links = WorkflowRunLinkRepository(session).list_by_entity(
            entity_type="llm_raw_output",
            entity_id=trace.id,
        )

    assert stored.request_id == "req_bound"
    assert stored.workflow_id == "wf_bound"
    assert stored.workflow_step == "memory_guard"
    assert stored.related_ids == {"memory_id": "mem_001"}
    assert len(trace_links) == 1
    assert trace_links[0].workflow_id == "wf_bound"
    assert trace_links[0].relation == "trace"


def test_workflow_run_repositories_transition_status_and_create_links() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        run_repository = WorkflowRunRepository(session)
        link_repository = WorkflowRunLinkRepository(session)
        run_repository.add(
            WorkflowRun(
                workflow_id="wf_repo",
                request_id="req_repo",
                workflow_type="memory.edit",
                status="running",
                persisted_ids={"memory_id": "mem_001"},
            )
        )
        link_repository.add(
            WorkflowRunLink(
                id="wflink_001",
                workflow_id="wf_repo",
                entity_type="memory",
                entity_id="mem_001",
                relation="updated",
            )
        )
        updated = run_repository.update_status(
            "wf_repo",
            status="completed",
            completed_at=run_repository.require("wf_repo").started_at,
            persisted_ids={"memory_id": "mem_001", "memory_ids": ["mem_001"]},
        )
        session.commit()

    with session_factory() as session:
        run_repository = WorkflowRunRepository(session)
        link_repository = WorkflowRunLinkRepository(session)
        stored = run_repository.require("wf_repo")
        by_request = run_repository.list_by_request("req_repo")
        links = link_repository.list_by_workflow("wf_repo")
        by_entity = link_repository.list_by_entity(
            entity_type="memory",
            entity_id="mem_001",
        )

    assert updated.status == "completed"
    assert stored.completed_at is not None
    assert stored.persisted_ids == {"memory_id": "mem_001", "memory_ids": ["mem_001"]}
    assert by_request[0].workflow_id == "wf_repo"
    assert links[0].relation == "updated"
    assert by_entity[0].workflow_id == "wf_repo"


def test_idempotency_record_repository_scopes_keys_by_workflow_type() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_conversation",
                request_id="req_create",
                workflow_type="conversation.create",
                status="completed",
            )
        )
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_memory",
                request_id="req_review",
                workflow_type="memory.review",
                status="completed",
            )
        )
        repository = IdempotencyRecordRepository(session)
        repository.add(
            IdempotencyRecord(
                id="idem_conversation",
                workflow_type="conversation.create",
                idempotency_key="retry-key",
                request_hash="a" * 64,
                request_id="req_create",
                workflow_id="wf_conversation",
                status="completed",
                response_status_code=201,
                replay_payload={
                    "request_id": "req_create",
                    "workflow_id": "wf_conversation",
                    "status": "completed",
                    "result": {"conversation": {"conversation_id": "conv_001"}},
                },
                related_ids={"conversation_id": "conv_001"},
            )
        )
        repository.add(
            IdempotencyRecord(
                id="idem_memory",
                workflow_type="memory.review",
                idempotency_key="retry-key",
                request_hash="b" * 64,
                request_id="req_review",
                workflow_id="wf_memory",
                status="completed",
                response_status_code=200,
                replay_payload={
                    "request_id": "req_review",
                    "workflow_id": "wf_memory",
                    "status": "completed",
                    "result": {"memory": {"id": "mem_001"}},
                },
                related_ids={"memory_id": "mem_001"},
            )
        )
        session.commit()

    with session_factory() as session:
        repository = IdempotencyRecordRepository(session)
        conversation_record = repository.find_by_scope(
            workflow_type="conversation.create",
            idempotency_key="retry-key",
        )
        memory_record = repository.find_by_scope(
            workflow_type="memory.review",
            idempotency_key="retry-key",
        )
        by_workflow = repository.list_by_workflow("wf_memory")

    assert conversation_record is not None
    assert conversation_record.workflow_id == "wf_conversation"
    assert conversation_record.response_status_code == 201
    assert conversation_record.replay_payload["result"]["conversation"]["conversation_id"] == (
        "conv_001"
    )
    assert memory_record is not None
    assert memory_record.workflow_id == "wf_memory"
    assert by_workflow[0].id == "idem_memory"


def test_retrieval_evaluation_repositories_roundtrip_run_and_cases() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Retrieval Work", source_type="markdown")
        )
        CharacterRepository(session).add(
            Character(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
            )
        )
        run = RetrievalEvaluationRun(
            id="retrievaleval_001",
            source_work_id="sw_001",
            character_id="char_001",
            test_suite="retrieval_suite",
            total_cases=1,
            embedding_model="fake-embedding",
        )
        RetrievalEvaluationRunRepository(session).add(run)
        RetrievalEvaluationCaseResultRepository(session).add(
            RetrievalEvaluationCaseResult(
                id="retrievalcase_001",
                run_id=run.id,
                case_id="claim_1",
                query="Lin Shuang observes before acting.",
                expected_chunk_ids=["chunk_001"],
                retrieved_chunk_ids=["chunk_001", "chunk_002"],
                retrieved_scores=[0.92, 0.2],
                status="passed",
                recall=1.0,
                first_relevant_rank=1,
                ranking_score=1.0,
                reasons=["recall=1.000"],
            )
        )
        updated = RetrievalEvaluationRunRepository(session).update_summary(
            run.id,
            status=EvaluationStatus.COMPLETED,
            passed_cases=1,
            failed_cases=0,
            completed_at=run.created_at,
        )
        session.commit()

    with session_factory() as session:
        run_repository = RetrievalEvaluationRunRepository(session)
        case_repository = RetrievalEvaluationCaseResultRepository(session)
        stored = run_repository.require("retrievaleval_001")
        recent = run_repository.list_recent(character_id="char_001", test_suite="retrieval_suite")
        cases = case_repository.list_by_run("retrievaleval_001")

    assert updated.status == "completed"
    assert stored.embedding_model == "fake-embedding"
    assert recent[0].id == "retrievaleval_001"
    assert cases[0].expected_chunk_ids == ["chunk_001"]
    assert cases[0].retrieved_scores == [0.92, 0.2]

