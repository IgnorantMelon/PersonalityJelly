from __future__ import annotations

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings
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
)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def _client(tmp_path) -> TestClient:
    resources = create_database_resources(f"sqlite:///{tmp_path / 'api-diagnostics.db'}")
    with resources.session_factory() as session:
        _seed_diagnostics_graph(session)
    app = create_app(settings=_settings(), database_resources=resources)
    return TestClient(app)


def test_critic_report_detail_resolves_message(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/critic-reports/cr_001")

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == "cr_001"
    assert body["message"]["id"] == "msg_assistant"
    assert body["message"]["context_package_id"] == "ctx_001"


def test_failure_case_routes_filter_and_return_detail_links(tmp_path) -> None:
    with _client(tmp_path) as client:
        list_response = client.get(
            "/failure-cases",
            params={"conversation_id": "conv_001", "category": "retry", "limit": 1},
        )
        detail_response = client.get("/failure-cases/fail_001")

    list_body = list_response.json()
    detail_body = detail_response.json()
    assert list_response.status_code == 200
    assert [item["id"] for item in list_body["items"]] == ["fail_001"]
    assert list_body["total_count"] == 1
    assert list_body["limit"] == 1
    assert detail_response.status_code == 200
    assert detail_body["user_message"]["content"] == "Hello"
    assert detail_body["assistant_message"]["content"] == "Generic assistant response"
    assert detail_body["context_package"]["id"] == "ctx_001"
    assert detail_body["critic_report"]["suggested_action"] == "retry"


def test_llm_trace_routes_filter_errors_and_return_raw_detail(tmp_path) -> None:
    with _client(tmp_path) as client:
        list_response = client.get(
            "/llm-traces",
            params={
                "provider_name": "stub",
                "schema_name": "MemoryGuardDecision",
                "with_errors": "true",
                "limit": 5,
            },
        )
        detail_response = client.get("/llm-traces/llm_trace_002")

    list_body = list_response.json()
    detail_body = detail_response.json()
    assert list_response.status_code == 200
    assert [item["id"] for item in list_body["items"]] == ["llm_trace_002"]
    assert list_body["items"][0]["validation_error_count"] == 1
    assert detail_response.status_code == 200
    assert detail_body["raw_output"] == '{"decision":"accept"}'
    assert detail_body["response_schema"] == {"title": "MemoryGuardDecision"}
    assert detail_body["parsed_output"] is None
    assert detail_body["validation_errors"] == ['{"loc":["reasoning"],"msg":"Field required"}']


def test_eval_run_routes_filter_and_apply_failed_only(tmp_path) -> None:
    with _client(tmp_path) as client:
        list_response = client.get(
            "/eval-runs",
            params={"character_id": "char_001", "test_suite": "boundary_regression"},
        )
        detail_response = client.get("/eval-runs/eval_001", params={"failed_only": "true"})

    list_body = list_response.json()
    detail_body = detail_response.json()
    assert list_response.status_code == 200
    assert [item["id"] for item in list_body["items"]] == ["eval_001"]
    assert detail_response.status_code == 200
    assert detail_body["diagnostics"]["total_cases"] == 1
    assert detail_body["diagnostics"]["failed_cases"] == 1
    assert [case["case_id"] for case in detail_body["cases"]] == ["failed_case"]
    assert detail_body["cases"][0]["conversation_id"] == "conv_001"
    assert detail_body["cases"][0]["context_package_id"] == "ctx_001"


def test_retrieval_eval_routes_filter_and_toggle_chunk_inclusion(tmp_path) -> None:
    with _client(tmp_path) as client:
        list_response = client.get(
            "/retrieval-eval-runs",
            params={
                "character_id": "char_001",
                "source_work_id": "sw_001",
                "test_suite": "retrieval_default",
            },
        )
        detail_response = client.get(
            "/retrieval-eval-runs/retrievaleval_001",
            params={"failed_only": "true", "include_chunks": "false"},
        )

    list_body = list_response.json()
    detail_body = detail_response.json()
    assert list_response.status_code == 200
    assert [item["id"] for item in list_body["items"]] == ["retrievaleval_001"]
    assert detail_response.status_code == 200
    assert detail_body["diagnostics"]["total_cases"] == 1
    assert detail_body["diagnostics"]["failed_cases"] == 1
    case = detail_body["cases"][0]
    assert case["case_id"] == "failed_case"
    assert case["missing_expected_chunk_ids"] == ["chunk_001"]
    assert case["expected_chunks"] == []
    assert case["retrieved_chunks"] == []


def test_diagnostic_detail_routes_return_not_found_envelopes(tmp_path) -> None:
    with _client(tmp_path) as client:
        responses = [
            client.get("/critic-reports/missing_critic"),
            client.get("/failure-cases/missing_failure"),
            client.get("/llm-traces/missing_trace"),
            client.get("/eval-runs/missing_eval"),
            client.get("/retrieval-eval-runs/missing_retrieval_eval"),
        ]

    for response in responses:
        body = response.json()
        assert response.status_code == 404
        assert body["error"]["code"] == "not_found"
        assert "missing" in body["error"]["message"]
        assert body["error"]["trace_id"] is None


def test_diagnostic_list_routes_reject_invalid_limits(tmp_path) -> None:
    with _client(tmp_path) as client:
        responses = [
            client.get("/failure-cases", params={"limit": 0}),
            client.get("/llm-traces", params={"limit": 0}),
            client.get("/eval-runs", params={"limit": 0}),
            client.get("/retrieval-eval-runs", params={"limit": 0}),
        ]

    for response in responses:
        body = response.json()
        assert response.status_code == 422
        assert body["error"]["code"] == "validation_error"
        assert body["error"]["details"]["errors"][0]["loc"] == ["query", "limit"]


def _seed_diagnostics_graph(session) -> None:
    _seed_runtime_graph(session)
    _seed_llm_traces(session)
    _seed_ooc_eval(session)
    _seed_retrieval_eval(session)
    session.commit()


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
    FailureCaseRepository(session).add(
        FailureCase(
            id="fail_002",
            conversation_id="conv_001",
            user_message_id="msg_user",
            assistant_message_id="msg_assistant",
            context_package_id="ctx_001",
            critic_report_id="cr_001",
            category="final",
            reason="Final response still broke character.",
        )
    )


def _seed_llm_traces(session) -> None:
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


def _seed_ooc_eval(session) -> None:
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
    EvaluationRunRepository(session).add(
        EvaluationRun(
            id="eval_002",
            character_id="char_other",
            persona_version_id="persona_other",
            test_suite="other_suite",
            status="completed",
            total_cases=0,
        )
    )


def _seed_retrieval_eval(session) -> None:
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
    RetrievalEvaluationRunRepository(session).add(
        RetrievalEvaluationRun(
            id="retrievaleval_002",
            source_work_id="sw_other",
            character_id="char_other",
            test_suite="other_suite",
            status="completed",
            total_cases=0,
        )
    )
