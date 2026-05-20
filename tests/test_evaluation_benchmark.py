from personality_jelly.characters import create_character
from personality_jelly.domain import ClaimStatus, ClaimType, EvaluationCaseStatus
from personality_jelly.evaluation import DEFAULT_OOC_BENCHMARK_CASES, run_ooc_benchmark
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import (
    CharacterRepository,
    EvaluationCaseResultRepository,
    EvaluationRunRepository,
    LLMRawOutputRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class ReaderFakeProvider:
    name = "reader-fake"

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "claims": [
                {
                    "claim_type": ClaimType.PERSONALITY,
                    "content": "林霜行事谨慎。",
                    "confidence": 0.9,
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.95,
                        }
                    ],
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class VerifierFakeProvider:
    name = "verifier-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        claim_id = next(
            line.split(": ", 1)[1]
            for line in messages[1].content.splitlines()
            if line.startswith("claim_id: ")
        )
        return {
            "decisions": [
                {
                    "claim_id": claim_id,
                    "status": ClaimStatus.VERIFIED,
                    "confidence": 0.95,
                    "reasoning": "证据直接支持。",
                }
            ],
            "conflicts": [],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CompilerFakeProvider:
    name = "compiler-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "core_self": "林霜谨慎敏锐。",
            "speech_rules": ["表达克制。"],
            "behavior_rules": ["先观察，再行动。"],
            "world_adaptation_rules": ["可以与现实用户交流。"],
            "forbidden_rules": ["不能改写原作经历。"],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class BenchmarkFakeProvider:
    name = "benchmark-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        return "我会先观察，再回答。"

    def generate_json(self, messages, schema, model_config):
        if schema.get("title") == "BenchmarkCaseEvaluation":
            return {
                "passed": True,
                "reasons": ["Fake benchmark evaluator accepted the response semantically."],
            }
        return {
            "ooc_risk": "low",
            "fact_risk": "low",
            "memory_risk": "low",
            "mode_risk": "low",
            "reasons": ["回复符合当前角色边界。"],
            "suggested_action": "accept",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_run_ooc_benchmark_persists_run_and_case_results(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="样本文本")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="林霜",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version

        result = run_ooc_benchmark(
            session,
            character_id="char_001",
            persona_version_id=persona.id,
            provider=BenchmarkFakeProvider(),
            model_config=ModelConfig(model="fake-benchmark"),
        )
        session.commit()

    with session_factory() as session:
        run = EvaluationRunRepository(session).require(result.run.id)
        case_results = EvaluationCaseResultRepository(session).list_by_run(run.id)
        traces = LLMRawOutputRepository(session).list_by_operation(
            "evaluation.benchmark.case_evaluation"
        )

    assert run.status == "completed"
    assert run.total_cases == len(DEFAULT_OOC_BENCHMARK_CASES)
    assert run.passed_cases == len(DEFAULT_OOC_BENCHMARK_CASES)
    assert run.failed_cases == 0
    assert len(case_results) == len(DEFAULT_OOC_BENCHMARK_CASES)
    assert {case.status for case in case_results} == {EvaluationCaseStatus.PASSED}
    assert case_results[-1].case_id == "joke_pollution"
    assert len(traces) == len(DEFAULT_OOC_BENCHMARK_CASES)
    assert traces[0].schema_name == "BenchmarkCaseEvaluation"
    assert traces[0].model_name == "fake-benchmark"
    assert traces[0].parsed_output["passed"] is True


def test_evaluation_run_repository_filters_recent_runs(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="sample")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version

        first = run_ooc_benchmark(
            session,
            character_id="char_001",
            persona_version_id=persona.id,
            provider=BenchmarkFakeProvider(),
            model_config=ModelConfig(model="fake-benchmark"),
            test_suite="suite_a",
        ).run
        second = run_ooc_benchmark(
            session,
            character_id="char_001",
            persona_version_id=persona.id,
            provider=BenchmarkFakeProvider(),
            model_config=ModelConfig(model="fake-benchmark"),
            test_suite="suite_b",
        ).run
        session.commit()

    with session_factory() as session:
        repository = EvaluationRunRepository(session)
        recent = repository.list_recent(limit=1, character_id="char_001")
        suite_a = repository.list_recent(test_suite="suite_a")

    assert recent[0].id == second.id
    assert suite_a[0].id == first.id
