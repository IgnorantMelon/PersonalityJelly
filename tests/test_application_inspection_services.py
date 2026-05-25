from __future__ import annotations

from personality_jelly.application import (
    get_critic_report_detail,
    get_evaluation_run_detail,
    get_failure_case_detail,
    get_llm_trace_detail,
    get_retrieval_evaluation_run_detail,
    list_failure_cases,
    list_llm_traces,
)
from personality_jelly.domain import (
    Character,
    ContextPackage,
    Conversation,
    CriticReport,
    EvaluationCaseResult,
    EvaluationRun,
    FailureCase,
    LLMRawOutput,
    Message,
    PersonaVersion,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRun,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.storage import (
    CharacterRepository,
    ContextPackageRepository,
    ConversationRepository,
    CriticReportRepository,
    EvaluationCaseResultRepository,
    EvaluationRunRepository,
    FailureCaseRepository,
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
    RetrievalEvaluationCaseResultRepository,
    RetrievalEvaluationRunRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_critic_and_failure_case_inspection_resolves_links() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_runtime_graph(session)
        critic_detail = get_critic_report_detail(session, "cr_001")
        failures = list_failure_cases(
            session,
            conversation_id="conv_001",
            category="retry",
            limit=10,
        )
        failure_detail = get_failure_case_detail(session, "fail_001")

    assert critic_detail.id == "cr_001"
    assert critic_detail.message is not None
    assert critic_detail.message.context_package_id == "ctx_001"
    assert failures.total_count == 1
    assert failures.items[0].id == "fail_001"
    assert failure_detail.user_message is not None
    assert failure_detail.user_message.content == "Hello"
    assert failure_detail.assistant_message is not None
    assert failure_detail.assistant_message.content == "Generic assistant response"
    assert failure_detail.context_package is not None
    assert failure_detail.context_package.id == "ctx_001"
    assert failure_detail.critic_report is not None
    assert failure_detail.critic_report.suggested_action == "retry"


def test_llm_trace_inspection_filters_errors_and_returns_detail() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        LLMRawOutputRepository(session).add(
            LLMRawOutput(
                id="llm_trace_001",
                operation="critic.evaluate_message",
                schema_name="CriticEvaluation",
                provider_name="stub",
                model_name="stub",
                response_schema={"title": "CriticEvaluation"},
                raw_output='{"suggested_action":"accept"}',
                parsed_output={"suggested_action": "accept"},
            )
        )
        LLMRawOutputRepository(session).add(
            LLMRawOutput(
                id="llm_trace_002",
                operation="memory.guard.semantic_decision",
                schema_name="MemoryGuardDecision",
                provider_name="stub",
                model_name="stub",
                response_schema={"title": "MemoryGuardDecision"},
                raw_output='{"decision":"accept"}',
                validation_errors=['{"loc":["reasoning"],"msg":"Field required"}'],
            )
        )
        session.commit()

        traces = list_llm_traces(session, with_errors=True, limit=20)
        detail = get_llm_trace_detail(session, "llm_trace_002")

    assert traces.total_count == 1
    assert traces.items[0].id == "llm_trace_002"
    assert traces.items[0].validation_error_count == 1
    assert detail.response_schema == {"title": "MemoryGuardDecision"}
    assert detail.raw_output == '{"decision":"accept"}'
    assert detail.parsed_output is None
    assert detail.validation_errors == ['{"loc":["reasoning"],"msg":"Field required"}']


def test_evaluation_run_detail_failed_only_links_assistant_context() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_runtime_graph(session)
        EvaluationRunRepository(session).add(
            EvaluationRun(
                id="eval_001",
                character_id="char_001",
                persona_version_id="persona_001",
                test_suite="boundary_regression",
                status="completed",
                total_cases=2,
                passed_cases=1,
                failed_cases=1,
            )
        )
        EvaluationCaseResultRepository(session).add(
            EvaluationCaseResult(
                id="evalcase_001",
                run_id="eval_001",
                case_id="passed_case",
                prompt="safe prompt",
                interaction_mode="reality_chat",
                assistant_message_id="msg_assistant",
                critic_report_id="cr_001",
                status="passed",
                category="ooc",
            )
        )
        EvaluationCaseResultRepository(session).add(
            EvaluationCaseResult(
                id="evalcase_002",
                run_id="eval_001",
                case_id="failed_case",
                prompt="unsafe prompt",
                interaction_mode="reality_chat",
                assistant_message_id="msg_assistant",
                critic_report_id="cr_001",
                status="failed",
                reasons=["response broke character"],
                category="ooc",
            )
        )
        session.commit()

        detail = get_evaluation_run_detail(session, "eval_001", failed_only=True)

    assert detail.id == "eval_001"
    assert detail.diagnostics is not None
    assert detail.diagnostics.total_cases == 1
    assert detail.diagnostics.failed_cases == 1
    assert len(detail.cases) == 1
    assert detail.cases[0].case_id == "failed_case"
    assert detail.cases[0].conversation_id == "conv_001"
    assert detail.cases[0].context_package_id == "ctx_001"
    assert detail.cases[0].assistant_message is not None
    assert detail.cases[0].assistant_message.id == "msg_assistant"


def test_retrieval_eval_detail_resolves_chunk_diagnostics() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_source_graph(session)
        RetrievalEvaluationRunRepository(session).add(
            RetrievalEvaluationRun(
                id="retrievaleval_001",
                source_work_id="sw_001",
                character_id="char_001",
                test_suite="retrieval_default",
                status="completed",
                total_cases=2,
                passed_cases=1,
                failed_cases=1,
                embedding_model="stub-embedding",
            )
        )
        RetrievalEvaluationCaseResultRepository(session).add(
            RetrievalEvaluationCaseResult(
                id="retrievalcase_001",
                run_id="retrievaleval_001",
                case_id="passed_case",
                query="observes before acting",
                expected_chunk_ids=["chunk_001"],
                retrieved_chunk_ids=["chunk_001"],
                retrieved_scores=[0.95],
                status="passed",
                recall=1.0,
                first_relevant_rank=1,
                ranking_score=1.0,
            )
        )
        RetrievalEvaluationCaseResultRepository(session).add(
            RetrievalEvaluationCaseResult(
                id="retrievalcase_002",
                run_id="retrievaleval_001",
                case_id="failed_case",
                query="observes before acting",
                expected_chunk_ids=["chunk_001"],
                retrieved_chunk_ids=["chunk_002"],
                retrieved_scores=[0.2],
                status="failed",
                recall=0.0,
                first_relevant_rank=None,
                ranking_score=0.0,
                reasons=["top-ranked chunk was not an expected evidence chunk"],
            )
        )
        session.commit()

        detail = get_retrieval_evaluation_run_detail(
            session,
            "retrievaleval_001",
            failed_only=True,
        )

    assert detail.diagnostics is not None
    assert detail.diagnostics.total_cases == 1
    assert detail.diagnostics.failed_cases == 1
    assert len(detail.cases) == 1
    case = detail.cases[0]
    assert case.case_id == "failed_case"
    assert case.expected_count == 1
    assert case.retrieved_count == 1
    assert case.top_retrieved_chunk_id == "chunk_002"
    assert case.missing_expected_chunk_ids == ["chunk_001"]
    assert case.top_retrieved_chunk_expected is False
    assert [chunk.id for chunk in case.expected_chunks] == ["chunk_001"]
    assert [chunk.id for chunk in case.retrieved_chunks] == ["chunk_002"]


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_source_graph(session) -> None:
    SourceWorkRepository(session).add(
        SourceWork(
            id="sw_001",
            title="Novel",
            source_type="markdown",
        )
    )
    SourceChunkRepository(session).add_many(
        [
            SourceChunk(
                id="chunk_001",
                source_work_id="sw_001",
                chapter_index=1,
                chapter_title="Chapter 1",
                paragraph_index=1,
                text="Lin Shuang observes before acting.",
            ),
            SourceChunk(
                id="chunk_002",
                source_work_id="sw_001",
                chapter_index=1,
                chapter_title="Chapter 1",
                paragraph_index=2,
                text="The room is quiet.",
            ),
        ]
    )
    CharacterRepository(session).add(
        Character(
            id="char_001",
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
        )
    )


def _seed_runtime_graph(session) -> None:
    _seed_source_graph(session)
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="persona_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="Careful observer.",
        )
    )
    UserRepository(session).add(User(id="user_001", display_name="User"))
    ConversationRepository(session).add(
        Conversation(
            id="conv_001",
            user_id="user_001",
            character_id="char_001",
            persona_version_id="persona_001",
        )
    )
    MessageRepository(session).add(
        Message(
            id="msg_user",
            conversation_id="conv_001",
            role="user",
            content="Hello",
        )
    )
    ContextPackageRepository(session).add(
        ContextPackage(
            id="ctx_001",
            conversation_id="conv_001",
            interaction_mode="reality_chat",
            persona_version_id="persona_001",
            claim_ids=[],
            memory_ids=[],
            retrieved_chunk_ids=["chunk_001"],
            assembled_prompt="prompt",
        )
    )
    MessageRepository(session).add(
        Message(
            id="msg_assistant",
            conversation_id="conv_001",
            role="assistant",
            content="Generic assistant response",
            context_package_id="ctx_001",
        )
    )
    CriticReportRepository(session).add(
        CriticReport(
            id="cr_001",
            message_id="msg_assistant",
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
            user_message_id="msg_user",
            assistant_message_id="msg_assistant",
            context_package_id="ctx_001",
            critic_report_id="cr_001",
            category="retry",
            reason="Assistant broke character.",
            notes="Captured rejected assistant response before retry.",
        )
    )
    session.commit()
