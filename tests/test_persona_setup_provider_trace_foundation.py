from pathlib import Path

import pytest

from personality_jelly.application import (
    PersonaSetupModelRoleBundle,
    PersonaSetupProviderRoleBundle,
    PersonaSetupTraceRecorders,
    build_character_persona,
    build_persona_setup_role_bundles,
    resolve_persona_setup_provider,
)
from personality_jelly.characters import create_character
from personality_jelly.core import Settings
from personality_jelly.domain import WorkflowRun
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.llm.tracing import RepositoryLLMTraceRecorder
from personality_jelly.storage import (
    LLMRawOutputRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class RecordingProvider:
    def __init__(self, name: str = "recording") -> None:
        self.name = name
        self.model_names: list[str] = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        self.model_names.append(model_config.model)
        schema_title = schema.get("title")
        if schema_title == "ReaderExtraction":
            chunk_id = _first_chunk_id(messages[-1].content)
            return {
                "claims": [
                    {
                        "claim_type": "personality",
                        "content": "Lin Shuang acts carefully.",
                        "confidence": 0.9,
                        "evidence": [
                            {
                                "chunk_id": chunk_id,
                                "excerpt": "Lin Shuang observes before acting.",
                                "support_score": 0.95,
                            }
                        ],
                    }
                ]
            }
        if schema_title == "VerifierResult":
            claim_id = next(
                line.split(": ", 1)[1]
                for line in messages[-1].content.splitlines()
                if line.startswith("claim_id: ")
            )
            return {
                "decisions": [
                    {
                        "claim_id": claim_id,
                        "status": "verified",
                        "confidence": 0.93,
                        "reasoning": "The evidence supports careful action.",
                    }
                ],
                "conflicts": [],
            }
        if schema_title == "PersonaCompilation":
            return {
                "core_self": "Lin Shuang is cautious and observant.",
                "speech_rules": ["Speak with restraint."],
                "behavior_rules": ["Observe before acting."],
                "world_adaptation_rules": ["Use canon experience to interpret new contexts."],
                "forbidden_rules": ["Do not rewrite canon events."],
            }
        raise AssertionError(f"Unexpected schema title: {schema_title!r}")

    def embed_texts(
        self,
        texts: list[str],
        embedding_config: EmbeddingConfig,
    ) -> list[list[float]]:
        raise NotImplementedError


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _first_chunk_id(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            return line.strip("[]")
    raise AssertionError("reader prompt did not include a chunk id")


def test_persona_setup_bundle_resolves_role_models_with_inheritance() -> None:
    provider = RecordingProvider()

    provider_roles, model_roles = build_persona_setup_role_bundles(
        provider=provider,
        model_config=ModelConfig(model="setup-default", temperature=0.3, max_tokens=512),
        role_models={
            "reader": "reader-model",
            "verifier": None,
            "persona_compiler": " ",
        },
    )

    assert provider_roles.reader is provider
    assert provider_roles.verifier is provider
    assert provider_roles.persona_compiler is provider
    assert model_roles.reader == ModelConfig(
        model="reader-model",
        temperature=0.3,
        max_tokens=512,
    )
    assert model_roles.verifier == ModelConfig(
        model="setup-default",
        temperature=0.3,
        max_tokens=512,
    )
    assert model_roles.persona_compiler == ModelConfig(
        model="setup-default",
        temperature=0.3,
        max_tokens=512,
    )


def test_resolve_persona_setup_provider_supports_stub_and_env() -> None:
    stub_roles, stub_models = resolve_persona_setup_provider(
        "stub",
        settings=_settings(),
        stub_provider_factory=lambda: RecordingProvider("stub-provider"),
    )

    assert stub_roles.reader.name == "stub-provider"
    assert stub_roles.verifier is stub_roles.reader
    assert stub_models.reader == ModelConfig(model="stub")
    assert stub_models.verifier == ModelConfig(model="stub")
    assert stub_models.persona_compiler == ModelConfig(model="stub")

    env_provider = RecordingProvider("env-provider")
    env_roles, env_models = resolve_persona_setup_provider(
        "env",
        settings=_settings(llm_model="bundle-model"),
        stub_provider_factory=lambda: RecordingProvider("unused-stub"),
        llm_provider_factory=lambda settings: env_provider,
        role_models={"verifier": "verifier-model"},
    )

    assert env_roles.reader is env_provider
    assert env_roles.verifier is env_provider
    assert env_roles.persona_compiler is env_provider
    assert env_models.reader == ModelConfig(model="bundle-model")
    assert env_models.verifier == ModelConfig(model="verifier-model")
    assert env_models.persona_compiler == ModelConfig(model="bundle-model")


def test_resolve_persona_setup_provider_rejects_unsupported_source() -> None:
    with pytest.raises(ValueError, match="unsupported provider source"):
        resolve_persona_setup_provider(
            "named_config",
            settings=_settings(llm_model="bundle-model"),
            stub_provider_factory=lambda: RecordingProvider("stub-provider"),
        )


def test_setup_steps_store_request_workflow_step_and_related_trace_ids(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# Chapter\n\nLin Shuang observes before acting.", encoding="utf-8")
    session_factory = _session_factory()

    reader = RecordingProvider("reader-provider")
    verifier = RecordingProvider("verifier-provider")
    compiler = RecordingProvider("compiler-provider")

    with session_factory() as session:
        ingestion = ingest_text_file(session, source_file, title="sample")
        source_work_id = ingestion.source_work.id
        create_character(
            session,
            source_work_id=source_work_id,
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        WorkflowRunRepository(session).add(
            WorkflowRun(
                workflow_id="wf_setup",
                request_id="req_setup",
                workflow_type="character_persona.setup",
                status="running",
                persisted_ids={
                    "source_work_id": source_work_id,
                    "character_id": "char_001",
                },
            )
        )
        trace_repository = LLMRawOutputRepository(session)
        related_ids = {
            "source_work_id": source_work_id,
            "character_id": "char_001",
        }

        result = build_character_persona(
            session,
            source_work_id=source_work_id,
            character_id="char_001",
            provider_roles=PersonaSetupProviderRoleBundle(
                reader=reader,
                verifier=verifier,
                persona_compiler=compiler,
            ),
            model_roles=PersonaSetupModelRoleBundle(
                reader=ModelConfig(model="reader-model"),
                verifier=ModelConfig(model="verifier-model"),
                persona_compiler=ModelConfig(model="compiler-model"),
            ),
            trace_recorders=PersonaSetupTraceRecorders(
                reader=RepositoryLLMTraceRecorder(
                    trace_repository,
                    request_id="req_setup",
                    workflow_id="wf_setup",
                    workflow_step="reader_extract",
                    related_ids=related_ids,
                ),
                verifier=RepositoryLLMTraceRecorder(
                    trace_repository,
                    request_id="req_setup",
                    workflow_id="wf_setup",
                    workflow_step="verifier_validate",
                    related_ids=related_ids,
                ),
                persona_compiler=RepositoryLLMTraceRecorder(
                    trace_repository,
                    request_id="req_setup",
                    workflow_id="wf_setup",
                    workflow_step="persona_compile",
                    related_ids=related_ids,
                ),
            ),
        )
        session.commit()

    with session_factory() as session:
        trace_repository = LLMRawOutputRepository(session)
        reader_trace = trace_repository.list_by_operation(
            "extraction.reader.extract_candidate_claims"
        )[0]
        verifier_trace = trace_repository.list_by_operation("extraction.verifier.verify_claim")[0]
        compiler_trace = trace_repository.list_by_operation("persona.compile_version")[0]
        trace_links = WorkflowRunLinkRepository(session).list_by_workflow("wf_setup")

    assert result.character_id == "char_001"
    assert result.persona_version_id.startswith("pv_")
    assert reader.model_names == ["reader-model"]
    assert verifier.model_names == ["verifier-model"]
    assert compiler.model_names == ["compiler-model"]
    assert (
        reader_trace.request_id,
        reader_trace.workflow_id,
        reader_trace.workflow_step,
        reader_trace.related_ids,
        reader_trace.provider_name,
        reader_trace.model_name,
    ) == (
        "req_setup",
        "wf_setup",
        "reader_extract",
        {"source_work_id": source_work_id, "character_id": "char_001"},
        "reader-provider",
        "reader-model",
    )
    assert verifier_trace.request_id == "req_setup"
    assert verifier_trace.workflow_id == "wf_setup"
    assert verifier_trace.workflow_step == "verifier_validate"
    assert verifier_trace.related_ids == reader_trace.related_ids
    assert verifier_trace.provider_name == "verifier-provider"
    assert verifier_trace.model_name == "verifier-model"
    assert compiler_trace.request_id == "req_setup"
    assert compiler_trace.workflow_id == "wf_setup"
    assert compiler_trace.workflow_step == "persona_compile"
    assert compiler_trace.related_ids == reader_trace.related_ids
    assert compiler_trace.provider_name == "compiler-provider"
    assert compiler_trace.model_name == "compiler-model"
    assert {
        (link.entity_type, link.entity_id, link.relation)
        for link in trace_links
    } == {
        ("llm_raw_output", reader_trace.id, "trace"),
        ("llm_raw_output", verifier_trace.id, "trace"),
        ("llm_raw_output", compiler_trace.id, "trace"),
    }
