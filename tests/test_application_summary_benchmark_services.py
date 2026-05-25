from __future__ import annotations

from personality_jelly.application import (
    dry_run_ooc_benchmark,
    dry_run_retrieval_benchmark,
    get_ooc_benchmark_report,
    get_retrieval_benchmark_report,
    run_ooc_benchmark_workflow,
    run_retrieval_benchmark_workflow,
    summarize_conversation_workflow,
)
from personality_jelly.domain import (
    CanonClaim,
    Character,
    ClaimStatus,
    ClaimType,
    EvidenceRef,
    InteractionMode,
    Message,
    MessageRole,
    PersonaVersion,
    SourceChunk,
    SourceWork,
    User,
)
from personality_jelly.evaluation import BenchmarkCase, RetrievalBenchmarkCase
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.runtime import create_conversation
from personality_jelly.runtime.summary import CONVERSATION_SUMMARY_OPERATION
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    EvaluationRunRepository,
    EvidenceRefRepository,
    LLMRawOutputRepository,
    MessageRepository,
    PersonaVersionRepository,
    RetrievalEvaluationRunRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    UserRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class SummaryFakeProvider:
    name = "summary-service-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "short_term_scene_state": "User is reviewing a quiet conversation.",
            "user_memory_candidates": ["User prefers late-night writing."],
            "relationship_memory_notes": ["User trusts the character with drafting."],
            "reflective_notes": ["Keep co-created fiction separate from canon."],
        }

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        raise NotImplementedError


class BenchmarkFakeProvider:
    name = "benchmark-service-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        return "Lin Shuang answers carefully and preserves the boundary."

    def generate_json(self, messages, schema, model_config):
        if schema.get("title") == "BenchmarkCaseEvaluation":
            return {
                "passed": True,
                "reasons": ["The response preserved character boundaries."],
            }
        return {
            "ooc_risk": "low",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["The response stayed inside the current mode."],
            "suggested_action": "accept",
        }

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        raise NotImplementedError


class RetrievalEmbeddingProvider:
    name = "retrieval-service-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        raise NotImplementedError

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        return [_vector_for_text(text) for text in texts]


def test_summarize_conversation_workflow_returns_inspection_detail() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_conversation(session)

        detail = summarize_conversation_workflow(
            session,
            conversation_id="conv_001",
            provider=SummaryFakeProvider(),
            model_config=ModelConfig(model="summary-service-model"),
            max_messages=2,
        )
        traces = LLMRawOutputRepository(session).list_by_operation(
            CONVERSATION_SUMMARY_OPERATION
        )

    assert detail.id == "conv_001"
    assert detail.summary is not None
    assert detail.summary.startswith("# Short-term Scene State")
    assert detail.summary_layers is not None
    assert detail.summary_layers.short_term_scene_state == (
        "User is reviewing a quiet conversation."
    )
    assert detail.summary_layers.user_memory_candidates == [
        "User prefers late-night writing."
    ]
    assert [message.id for message in detail.messages] == ["msg_001", "msg_002"]
    assert detail.user is not None
    assert detail.character is not None
    assert detail.persona_version is not None
    assert len(traces) == 1
    assert traces[0].schema_name == "ConversationSummaryDraft"
    assert traces[0].model_name == "summary-service-model"


def test_dry_run_ooc_benchmark_reports_cases_without_creating_run() -> None:
    cases = (
        BenchmarkCase(
            id="manual_reality",
            prompt="Who are you?",
            interaction_mode=InteractionMode.REALITY_CHAT,
            category="ooc",
        ),
        BenchmarkCase(
            id="manual_scene",
            prompt="Enter a source scene.",
            interaction_mode=InteractionMode.ROLEPLAY_SCENE,
            category="mode_confusion",
        ),
    )
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_character_with_persona(session)

        result = dry_run_ooc_benchmark(
            session,
            character_id="char_001",
            cases=cases,
        )
        runs = EvaluationRunRepository(session).list_recent()

    assert result.character_id == "char_001"
    assert result.persona_version_id == "persona_001"
    assert result.case_suite is None
    assert result.cases_source == "explicit"
    assert result.will_create_run is False
    assert result.cases_summary.total_cases == 2
    assert [case.id for case in result.cases] == ["manual_reality", "manual_scene"]
    assert {report.interaction_mode for report in result.cases_summary.mode_reports} == {
        "reality_chat",
        "roleplay_scene",
    }
    assert runs == []


def test_run_ooc_benchmark_workflow_returns_report_detail() -> None:
    cases = (
        BenchmarkCase(
            id="manual_boundary",
            prompt="Please preserve the boundary.",
            interaction_mode=InteractionMode.REALITY_CHAT,
            category="ooc",
        ),
    )
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_character_with_persona(session)

        detail = run_ooc_benchmark_workflow(
            session,
            character_id="char_001",
            persona_version_id="persona_001",
            provider=BenchmarkFakeProvider(),
            model_config=ModelConfig(model="benchmark-service-model"),
            test_suite="service_ooc",
            cases=cases,
        )
        report = get_ooc_benchmark_report(session, detail.id)
        failed_report = get_ooc_benchmark_report(session, detail.id, failed_only=True)

    assert detail.status == "completed"
    assert detail.test_suite == "service_ooc"
    assert detail.total_cases == 1
    assert detail.passed_cases == 1
    assert detail.failed_cases == 0
    assert detail.diagnostics is not None
    assert detail.diagnostics.total_cases == 1
    assert len(detail.cases) == 1
    assert detail.cases[0].case_id == "manual_boundary"
    assert detail.cases[0].conversation_id is not None
    assert detail.cases[0].context_package_id is not None
    assert detail.cases[0].assistant_message is not None
    assert report.id == detail.id
    assert failed_report.cases == []
    assert failed_report.diagnostics is not None
    assert failed_report.diagnostics.total_cases == 0


def test_dry_run_retrieval_benchmark_reports_generated_cases_without_run() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_retrieval_graph(session)

        result = dry_run_retrieval_benchmark(
            session,
            character_id="char_001",
            max_cases=1,
            include_empty_case=True,
            embedding_config=EmbeddingConfig(model="service-embedding"),
        )
        runs = RetrievalEvaluationRunRepository(session).list_recent()

    assert result.source_work_id == "sw_001"
    assert result.character_id == "char_001"
    assert result.embedding_model == "service-embedding"
    assert result.cases_source == "generated"
    assert result.will_create_run is False
    assert result.cases_summary.total_cases == 2
    assert result.cases_summary.evidence_case_count == 1
    assert result.cases_summary.empty_case_count == 1
    assert result.cases_summary.expected_chunk_ref_count == 1
    assert [case.id for case in result.cases] == ["claim_1", "empty_result"]
    assert runs == []


def test_run_retrieval_benchmark_workflow_returns_report_detail() -> None:
    cases = (
        RetrievalBenchmarkCase(
            id="manual_evidence",
            query="How does Lin Shuang decide?",
            expected_chunk_ids=("chunk_001",),
            limit=1,
        ),
    )
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_retrieval_graph(session)

        detail = run_retrieval_benchmark_workflow(
            session,
            character_id="char_001",
            provider=RetrievalEmbeddingProvider(),
            embedding_config=EmbeddingConfig(model="service-embedding"),
            test_suite="service_retrieval",
            cases=cases,
        )
        report = get_retrieval_benchmark_report(session, detail.id)
        id_only_report = get_retrieval_benchmark_report(
            session,
            detail.id,
            include_chunks=False,
        )

    assert detail.status == "completed"
    assert detail.test_suite == "service_retrieval"
    assert detail.embedding_model == "service-embedding"
    assert detail.total_cases == 1
    assert detail.passed_cases == 1
    assert detail.failed_cases == 0
    assert detail.diagnostics is not None
    assert detail.diagnostics.total_cases == 1
    assert len(detail.cases) == 1
    case = detail.cases[0]
    assert case.case_id == "manual_evidence"
    assert case.expected_count == 1
    assert case.retrieved_count == 1
    assert case.top_retrieved_chunk_id == "chunk_001"
    assert [chunk.id for chunk in case.expected_chunks] == ["chunk_001"]
    assert [chunk.id for chunk in case.retrieved_chunks] == ["chunk_001"]
    assert report.id == detail.id
    assert id_only_report.cases[0].expected_chunks == []
    assert id_only_report.cases[0].retrieved_chunks == []


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_conversation(session) -> None:
    _seed_character_with_persona(session)
    UserRepository(session).add(User(id="user_001", display_name="Tester"))
    create_conversation(
        session,
        conversation_id="conv_001",
        user_id="user_001",
        character_id="char_001",
        persona_version_id="persona_001",
    )
    MessageRepository(session).add(
        Message(
            id="msg_001",
            conversation_id="conv_001",
            role=MessageRole.USER,
            content="Please remember that I write at night.",
        )
    )
    MessageRepository(session).add(
        Message(
            id="msg_002",
            conversation_id="conv_001",
            role=MessageRole.ASSISTANT,
            content="I will keep that separate from canon.",
        )
    )
    session.commit()


def _seed_character_with_persona(session) -> None:
    SourceWorkRepository(session).add(
        SourceWork(id="sw_001", title="Service Test Novel", source_type="markdown")
    )
    SourceChunkRepository(session).add_many(
        [
            SourceChunk(
                id="chunk_001",
                source_work_id="sw_001",
                paragraph_index=1,
                text="Lin Shuang watches the window before making a decision.",
            ),
            SourceChunk(
                id="chunk_002",
                source_work_id="sw_001",
                paragraph_index=2,
                text="The bell rings over an empty street.",
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
    PersonaVersionRepository(session).add(
        PersonaVersion(
            id="persona_001",
            character_id="char_001",
            source_work_id="sw_001",
            version_number=1,
            core_self="Careful observer.",
            speech_rules=["Speak with restraint."],
            behavior_rules=["Observe before acting."],
            world_adaptation_rules=["Treat the user as real conversation context."],
            forbidden_rules=["Do not rewrite source canon."],
        )
    )


def _seed_retrieval_graph(session) -> None:
    _seed_character_with_persona(session)
    CanonClaimRepository(session).add(
        CanonClaim(
            id="claim_001",
            source_work_id="sw_001",
            character_id="char_001",
            claim_type=ClaimType.PERSONALITY,
            content="Lin Shuang observes before acting.",
            status=ClaimStatus.VERIFIED,
            confidence=0.9,
            created_by="reader",
        )
    )
    EvidenceRefRepository(session).add(
        EvidenceRef(
            id="evidence_001",
            claim_id="claim_001",
            chunk_id="chunk_001",
            excerpt="watches the window before making a decision",
            support_score=0.95,
        )
    )
    session.commit()


def _vector_for_text(text: str) -> list[float]:
    if "user_query" in text:
        return [1.0, 0.0]
    if text == "Lin Shuang watches the window before making a decision.":
        return [1.0, 0.0]
    if text == "The bell rings over an empty street.":
        return [0.0, 1.0]
    return [0.0, 0.0]
