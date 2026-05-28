from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from personality_jelly.application import (
    CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    LocalActorContext,
    PersonaSetupModelRoleBundle,
    PersonaSetupProviderRoleBundle,
    CharacterPersonaSetupReplay,
    CharacterPersonaSetupWorkflowRequest,
    build_idempotency_context,
    run_character_persona_setup_workflow,
)
from personality_jelly.characters import create_character
from personality_jelly.domain import SourceWork
from personality_jelly.ingestion import ChunkingConfig, LoadedSource, ingest_loaded_source
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    AuditEventRepository,
    CanonClaimRepository,
    ClaimConflictRepository,
    EvidenceRefRepository,
    IdempotencyRecordRepository,
    LLMRawOutputRepository,
    PersonaVersionRepository,
    SourceWorkRepository,
    WorkflowRunLinkRepository,
    WorkflowRunRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


@dataclass
class SetupWorkflowProvider:
    name: str = "setup-workflow-provider"
    schema_titles: list[str] | None = None

    def __post_init__(self) -> None:
        if self.schema_titles is None:
            self.schema_titles = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        self.schema_titles.append(schema_title)
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
                    },
                    {
                        "claim_type": "event",
                        "content": "Lin Shuang rushes into danger.",
                        "confidence": 0.4,
                        "evidence": [
                            {
                                "chunk_id": chunk_id,
                                "excerpt": "Lin Shuang observes before acting.",
                                "support_score": 0.2,
                            }
                        ],
                    },
                ]
            }
        if schema_title == "VerifierResult":
            careful_claim_id, reckless_claim_id = _claim_ids_from_prompt(messages[-1].content)
            return {
                "decisions": [
                    {
                        "claim_id": careful_claim_id,
                        "status": "verified",
                        "confidence": 0.93,
                        "reasoning": "The evidence supports careful action.",
                    },
                    {
                        "claim_id": reckless_claim_id,
                        "status": "conflicted",
                        "confidence": 0.25,
                        "reasoning": "The evidence conflicts with reckless action.",
                    },
                ],
                "conflicts": [
                    {
                        "claim_a_id": careful_claim_id,
                        "claim_b_id": reckless_claim_id,
                        "description": "Careful and reckless behavior conflict.",
                        "resolution": "Keep the careful behavior claim.",
                    }
                ],
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


class ExplodingProvider(SetupWorkflowProvider):
    def generate_json(self, messages, schema, model_config):
        raise AssertionError("provider should not be called during idempotency replay")


class TransportFailureProvider(SetupWorkflowProvider):
    def __init__(self, fail_schema_title: str) -> None:
        super().__init__()
        self.fail_schema_title = fail_schema_title

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        if schema_title == self.fail_schema_title:
            self.schema_titles.append(schema_title)
            raise RuntimeError(
                "provider transport failed with api_key=sk-raw-secret "
                r"and path C:\Users\figna\provider.log"
            )
        return super().generate_json(messages, schema, model_config)


class ValidationFailureProvider(SetupWorkflowProvider):
    def __init__(self, fail_schema_title: str) -> None:
        super().__init__()
        self.fail_schema_title = fail_schema_title

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        if schema_title == self.fail_schema_title:
            self.schema_titles.append(schema_title)
            return {
                "raw_provider_output": "RAW_PROVIDER_OUTPUT_SHOULD_NOT_LEAK",
                "source_text": "Lin Shuang observes before acting.",
                "claims": "not-a-list",
                "decisions": "not-a-list",
                "core_self": 123,
            }
        return super().generate_json(messages, schema, model_config)


class NoVerifiedProvider(SetupWorkflowProvider):
    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        if schema_title == "VerifierResult":
            self.schema_titles.append(schema_title)
            careful_claim_id, reckless_claim_id = _claim_ids_from_prompt(messages[-1].content)
            return {
                "decisions": [
                    {
                        "claim_id": careful_claim_id,
                        "status": "rejected",
                        "confidence": 0.2,
                        "reasoning": "The evidence was too weak.",
                    },
                    {
                        "claim_id": reckless_claim_id,
                        "status": "conflicted",
                        "confidence": 0.25,
                        "reasoning": "The evidence conflicts with the claim.",
                    },
                ],
                "conflicts": [
                    {
                        "claim_a_id": careful_claim_id,
                        "claim_b_id": reckless_claim_id,
                        "description": "No claim is verified.",
                        "resolution": "Review the source and aliases.",
                    }
                ],
            }
        return super().generate_json(messages, schema, model_config)


def test_successful_setup_persists_domain_rows_workflow_links_audit_and_replay() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = SetupWorkflowProvider()
        request = _request(provider=provider)

        result = run_character_persona_setup_workflow(session, request)

        claims = CanonClaimRepository(session).list_by_character("char_setup")
        evidence_refs = EvidenceRefRepository(session).list_all()
        conflicts = ClaimConflictRepository(session).list_all()
        persona = PersonaVersionRepository(session).require(result.persisted_ids.persona_version_id)
        traces = LLMRawOutputRepository(session).list_all()
        audit = AuditEventRepository(session).require(result.persisted_ids.audit_event_ids[0])
        workflow = WorkflowRunRepository(session).require(result.workflow_id)
        workflow_links = WorkflowRunLinkRepository(session).list_by_workflow(result.workflow_id)
        replay_records = IdempotencyRecordRepository(session).list_all()

    claim_ids = {claim.id for claim in claims}
    evidence_ref_ids = {evidence.id for evidence in evidence_refs}
    conflict_ids = {conflict.id for conflict in conflicts}
    trace_ids = {trace.id for trace in traces}
    verified_claim_ids = {claim.id for claim in claims if claim.status == "verified"}

    assert result.request_id == "req_setup"
    assert result.workflow_type == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert result.status == "completed"
    assert result.ids.source_work_id == "sw_setup"
    assert result.ids.character_id == "char_setup"
    assert result.ids.persona_version_id == persona.id
    assert result.persisted_ids.source_work_id == "sw_setup"
    assert result.persisted_ids.character_id == "char_setup"
    assert set(result.persisted_ids.candidate_claim_ids) == claim_ids
    assert set(result.persisted_ids.evidence_ref_ids) == evidence_ref_ids
    assert set(result.persisted_ids.verified_claim_ids) == verified_claim_ids
    assert set(result.persisted_ids.conflict_ids) == conflict_ids
    assert result.persisted_ids.persona_version_id == persona.id
    assert set(result.persisted_ids.llm_trace_ids) == trace_ids
    assert result.counts.model_dump(mode="json") == {
        "candidate_claims": 2,
        "evidence_refs": 2,
        "verified_claims": 1,
        "conflicts": 1,
        "llm_traces": 3,
        "audit_events": 1,
    }
    assert result.redaction.source_text_redacted is True
    assert result.redaction.evidence_excerpt_redacted is True
    assert provider.schema_titles == [
        "ReaderExtraction",
        "VerifierResult",
        "PersonaCompilation",
    ]

    assert set(persona.source_claim_ids) == set(result.persisted_ids.verified_claim_ids)
    assert audit.operation == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert audit.result == "succeeded"
    assert audit.entity_type == "character"
    assert audit.entity_id == "char_setup"
    assert audit.request_id == "req_setup"
    assert audit.workflow_id == result.workflow_id
    assert audit.related_ids == {
        "source_work_id": "sw_setup",
        "character_id": "char_setup",
        "persona_version_id": persona.id,
    }
    assert audit.after["counts"]["verified_claims"] == 1
    assert audit.after["redaction"]["prompts_redacted"] is True
    assert audit.metadata["client_metadata"] == {"client_label": "workflow-test"}
    assert "Lin Shuang observes before acting." not in str(audit.after) + str(audit.metadata)

    assert workflow.status == "completed"
    assert workflow.workflow_type == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert workflow.persisted_ids["source_work_id"] == "sw_setup"
    assert workflow.persisted_ids["character_id"] == "char_setup"
    assert workflow.persisted_ids["persona_version_id"] == persona.id
    assert workflow.persisted_ids["llm_trace_ids"] == result.persisted_ids.llm_trace_ids
    assert workflow.persisted_ids["audit_event_ids"] == result.persisted_ids.audit_event_ids

    assert {(trace.workflow_step, trace.request_id, trace.workflow_id) for trace in traces} == {
        ("reader_extract", "req_setup", result.workflow_id),
        ("verifier_validate", "req_setup", result.workflow_id),
        ("persona_compile", "req_setup", result.workflow_id),
    }
    assert all(
        trace.related_ids == {"source_work_id": "sw_setup", "character_id": "char_setup"}
        for trace in traces
    )

    assert _link_set(workflow_links) == {
        ("source_work", "sw_setup", "input"),
        ("character", "char_setup", "input"),
        *(("llm_raw_output", trace.id, "trace") for trace in traces),
        *(("canon_claim", claim.id, "candidate_claim") for claim in claims),
        *(("evidence_ref", evidence.id, "evidence") for evidence in evidence_refs),
        *(("canon_claim", claim_id, "verified_claim") for claim_id in verified_claim_ids),
        *(("claim_conflict", conflict.id, "conflict") for conflict in conflicts),
        ("persona_version", persona.id, "created"),
        ("audit_event", audit.id, "audit"),
        ("idempotency_record", replay_records[0].id, "idempotency"),
    }

    assert len(replay_records) == 1
    replay = replay_records[0]
    assert replay.workflow_type == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert replay.idempotency_key == "setup-key"
    assert replay.response_status_code == 201
    assert replay.replay_payload["request_id"] == "req_setup"
    assert replay.replay_payload["workflow_id"] == result.workflow_id
    assert replay.replay_payload["result"]["persisted_ids"] == result.persisted_ids.model_dump(
        mode="json"
    )
    assert replay.related_ids["candidate_claim_ids"] == result.persisted_ids.candidate_claim_ids
    assert "Lin Shuang observes before acting." not in str(replay.replay_payload)


def test_reader_transport_failure_marks_workflow_failed_without_business_rows() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = TransportFailureProvider("ReaderExtraction")

        result = run_character_persona_setup_workflow(session, _request(provider=provider))

        workflow = WorkflowRunRepository(session).require(result.workflow_id)
        audit = AuditEventRepository(session).require(result.persisted_ids.audit_event_ids[0])
        replay = IdempotencyRecordRepository(session).list_all()[0]

        assert result.status == "failed"
        assert result.failure.error_family == "provider_failure"
        assert result.failure.error_code == "provider_failure"
        assert result.failure.failed_step == "reader_extract"
        assert result.failure.retry_hint == "inspect_workflow_and_retry_with_new_idempotency_key"
        assert result.counts.model_dump(mode="json") == {
            "candidate_claims": 0,
            "evidence_refs": 0,
            "verified_claims": 0,
            "conflicts": 0,
            "llm_traces": 0,
            "audit_events": 1,
        }
        assert workflow.status == "failed"
        assert workflow.error_code == "provider_failure"
        assert workflow.failed_step == "reader_extract"
        assert audit.result == "failed"
        assert replay.status == "failed"
        assert replay.response_status_code == 502
        assert replay.replay_payload["error"]["code"] == "provider_failure"
        assert provider.schema_titles == ["ReaderExtraction"]
        assert _counts(session) == {
            "claims": 0,
            "evidence": 0,
            "conflicts": 0,
            "personas": 0,
            "traces": 0,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_reader_validation_failure_returns_safe_trace_id_without_raw_output() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = ValidationFailureProvider("ReaderExtraction")

        result = run_character_persona_setup_workflow(session, _request(provider=provider))

        traces = LLMRawOutputRepository(session).list_all()
        workflow = WorkflowRunRepository(session).require(result.workflow_id)
        replay = IdempotencyRecordRepository(session).list_all()[0]

        assert result.status == "failed"
        assert result.failure.error_family == "provider_validation_error"
        assert result.failure.error_code == "provider_validation_error"
        assert result.failure.failed_step == "reader_extract"
        assert result.failure.llm_trace_ids == [traces[0].id]
        assert workflow.status == "failed"
        assert workflow.error_code == "provider_validation_error"
        assert workflow.persisted_ids["llm_trace_ids"] == [traces[0].id]
        assert replay.replay_payload["error"]["details"]["llm_trace_ids"] == [traces[0].id]
        assert "RAW_PROVIDER_OUTPUT_SHOULD_NOT_LEAK" not in _serialized(
            {
                "result": result.model_dump(mode="json"),
                "workflow_error": workflow.error_details,
                "replay": replay.model_dump(mode="json"),
            }
        )
        assert _counts(session) == {
            "claims": 0,
            "evidence": 0,
            "conflicts": 0,
            "personas": 0,
            "traces": 1,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_verifier_validation_failure_after_reader_persistence_marks_partial() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = ValidationFailureProvider("VerifierResult")

        result = run_character_persona_setup_workflow(session, _request(provider=provider))

        workflow = WorkflowRunRepository(session).require(result.workflow_id)
        replay = IdempotencyRecordRepository(session).list_all()[0]

        assert result.status == "partial"
        assert result.failure.error_family == "partial_persistence"
        assert result.failure.error_code == "provider_validation_error"
        assert result.failure.failed_step == "verifier_validate"
        assert result.persisted_ids.candidate_claim_ids
        assert result.persisted_ids.evidence_ref_ids
        assert result.persisted_ids.persona_version_id is None
        assert result.counts.candidate_claims == 2
        assert result.counts.evidence_refs == 2
        assert result.counts.llm_traces == 2
        assert workflow.status == "partial"
        assert workflow.error_code == "partial_persistence"
        assert replay.status == "partial"
        assert replay.response_status_code == 500
        assert replay.replay_payload["error"]["code"] == "partial_persistence"
        assert provider.schema_titles == ["ReaderExtraction", "VerifierResult"]
        assert _counts(session) == {
            "claims": 2,
            "evidence": 2,
            "conflicts": 0,
            "personas": 0,
            "traces": 2,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_no_verified_claims_after_verifier_marks_partial_without_compiling() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = NoVerifiedProvider()

        result = run_character_persona_setup_workflow(session, _request(provider=provider))

        claims = CanonClaimRepository(session).list_by_character("char_setup")
        workflow = WorkflowRunRepository(session).require(result.workflow_id)

        assert result.status == "partial"
        assert result.failure.error_family == "partial_persistence"
        assert result.failure.error_code == "no_verified_claims"
        assert result.failure.failed_step == "persona_compile"
        assert result.persisted_ids.verified_claim_ids == []
        assert result.persisted_ids.conflict_ids
        assert result.persisted_ids.persona_version_id is None
        assert workflow.status == "partial"
        assert all(claim.status != "verified" for claim in claims)
        assert "PersonaCompilation" not in provider.schema_titles
        assert _counts(session)["personas"] == 0


def test_compiler_validation_failure_after_verification_marks_partial() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        provider = ValidationFailureProvider("PersonaCompilation")

        result = run_character_persona_setup_workflow(session, _request(provider=provider))

        workflow = WorkflowRunRepository(session).require(result.workflow_id)

        assert result.status == "partial"
        assert result.failure.error_family == "partial_persistence"
        assert result.failure.error_code == "provider_validation_error"
        assert result.failure.failed_step == "persona_compile"
        assert result.persisted_ids.verified_claim_ids
        assert result.persisted_ids.persona_version_id is None
        assert result.counts.llm_traces == 3
        assert workflow.status == "partial"
        assert workflow.error_code == "partial_persistence"
        assert provider.schema_titles == [
            "ReaderExtraction",
            "VerifierResult",
            "PersonaCompilation",
        ]
        assert _counts(session)["personas"] == 0


def test_terminal_failed_replay_returns_stored_payload_without_provider_calls() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        first = run_character_persona_setup_workflow(
            session,
            _request(provider=TransportFailureProvider("ReaderExtraction")),
        )
        replay_payload = IdempotencyRecordRepository(session).list_all()[0].replay_payload

        replay = run_character_persona_setup_workflow(
            session,
            _request(
                provider=ExplodingProvider(),
                correlation=CorrelationContext(request_id="req_failed_replay_attempt"),
            ),
        )

        assert isinstance(replay, CharacterPersonaSetupReplay)
        assert first.status == "failed"
        assert replay.response_status_code == 502
        assert replay.replay_payload == replay_payload
        assert replay.replay_payload["error"]["code"] == "provider_failure"
        assert _counts(session) == {
            "claims": 0,
            "evidence": 0,
            "conflicts": 0,
            "personas": 0,
            "traces": 0,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_terminal_partial_replay_returns_stored_payload_without_resuming() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        first = run_character_persona_setup_workflow(
            session,
            _request(provider=ValidationFailureProvider("VerifierResult")),
        )
        replay_payload = IdempotencyRecordRepository(session).list_all()[0].replay_payload

        replay = run_character_persona_setup_workflow(
            session,
            _request(
                provider=ExplodingProvider(),
                correlation=CorrelationContext(request_id="req_partial_replay_attempt"),
            ),
        )

        assert isinstance(replay, CharacterPersonaSetupReplay)
        assert first.status == "partial"
        assert replay.response_status_code == 500
        assert replay.replay_payload == replay_payload
        assert replay.replay_payload["error"]["code"] == "partial_persistence"
        assert _counts(session) == {
            "claims": 2,
            "evidence": 2,
            "conflicts": 0,
            "personas": 0,
            "traces": 2,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_terminal_failure_partial_payloads_are_recursively_redacted() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        result = run_character_persona_setup_workflow(
            session,
            _request(provider=ValidationFailureProvider("ReaderExtraction")),
        )

        trace = LLMRawOutputRepository(session).list_all()[0]
        workflow = WorkflowRunRepository(session).require(result.workflow_id)
        audit = AuditEventRepository(session).require(result.persisted_ids.audit_event_ids[0])
        replay = IdempotencyRecordRepository(session).list_all()[0]
        payload = {
            "result": result.model_dump(mode="json"),
            "workflow_error": workflow.error_details,
            "audit_metadata": audit.metadata,
            "idempotency": replay.model_dump(mode="json"),
            "trace_reference": {
                "id": trace.id,
                "request_id": trace.request_id,
                "workflow_id": trace.workflow_id,
                "workflow_step": trace.workflow_step,
                "related_ids": trace.related_ids,
            },
        }
        serialized = _serialized(payload)

        assert result.failure.llm_trace_ids == [trace.id]
        for forbidden in [
            "RAW_PROVIDER_OUTPUT_SHOULD_NOT_LEAK",
            "Lin Shuang observes before acting.",
            '"raw_output"',
            '"parsed_output"',
            '"response_schema"',
            '"validation_errors"',
            '"provider_payload"',
            '"provider_config"',
            "api_key",
            "authorization",
            "Traceback",
            "C:\\Users",
            "SELECT ",
        ]:
            assert forbidden not in serialized


def test_terminal_success_replay_returns_stored_payload_without_provider_calls() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        first = run_character_persona_setup_workflow(
            session,
            _request(provider=SetupWorkflowProvider()),
        )
        replay_payload = IdempotencyRecordRepository(session).list_all()[0].replay_payload
        replay = run_character_persona_setup_workflow(
            session,
            _request(
                provider=ExplodingProvider(),
                correlation=CorrelationContext(request_id="req_replay_attempt"),
            ),
        )

        assert isinstance(replay, CharacterPersonaSetupReplay)
        assert replay.response_status_code == 201
        assert replay.replay_payload == replay_payload
        assert replay.replay_payload["request_id"] == first.request_id
        assert _counts(session) == {
            "claims": 2,
            "evidence": 2,
            "conflicts": 1,
            "personas": 1,
            "traces": 3,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_idempotency_hash_mismatch_returns_conflict_without_provider_calls() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        run_character_persona_setup_workflow(session, _request(provider=SetupWorkflowProvider()))

        with pytest.raises(ConflictError, match="different request input"):
            run_character_persona_setup_workflow(
                session,
                _request(
                    provider=ExplodingProvider(),
                    idempotency_key="setup-key",
                    request_hash_payload={
                        "source_work_id": "sw_setup",
                        "character_id": "char_setup",
                        "workflow_options": {"max_chunks": 2},
                    },
                ),
            )

        assert _counts(session) == {
            "claims": 2,
            "evidence": 2,
            "conflicts": 1,
            "personas": 1,
            "traces": 3,
            "audits": 1,
            "workflows": 1,
            "idempotency_records": 1,
        }


def test_source_character_mismatch_fails_before_setup_business_rows() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)
        SourceWorkRepository(session).add(
            SourceWork(id="sw_other", title="Other", source_type="markdown")
        )
        session.commit()

        with pytest.raises(ValueError, match="does not belong to source work"):
            run_character_persona_setup_workflow(
                session,
                _request(
                    source_work_id="sw_other",
                    request_hash_payload={
                        "source_work_id": "sw_other",
                        "character_id": "char_setup",
                        "workflow_options": {"max_chunks": 1},
                    },
                ),
            )

        assert _counts(session) == {
            "claims": 0,
            "evidence": 0,
            "conflicts": 0,
            "personas": 0,
            "traces": 0,
            "audits": 0,
            "workflows": 0,
            "idempotency_records": 0,
        }


def test_invalid_max_chunks_fails_before_setup_business_rows() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        _seed_source_and_character(session)

        with pytest.raises(ValueError, match="max_chunks must be a positive integer"):
            run_character_persona_setup_workflow(
                session,
                _request(
                    max_chunks=0,
                    request_hash_payload={
                        "source_work_id": "sw_setup",
                        "character_id": "char_setup",
                        "workflow_options": {"max_chunks": 0},
                    },
                ),
            )

        assert _counts(session) == {
            "claims": 0,
            "evidence": 0,
            "conflicts": 0,
            "personas": 0,
            "traces": 0,
            "audits": 0,
            "workflows": 0,
            "idempotency_records": 0,
        }


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def _seed_source_and_character(session) -> None:
    ingest_loaded_source(
        session,
        LoadedSource(
            title="Inline Source",
            source_type="markdown",
            text="# Chapter\n\nLin Shuang observes before acting.\n\nThen she waits.",
            path=None,
        ),
        source_work_id="sw_setup",
        chunking_config=ChunkingConfig(max_paragraph_chars=500, min_paragraph_chars=1),
    )
    create_character(
        session,
        source_work_id="sw_setup",
        canonical_name="Lin Shuang",
        character_id="char_setup",
    )
    session.commit()


def _request(
    *,
    provider: SetupWorkflowProvider | None = None,
    source_work_id: str = "sw_setup",
    character_id: str = "char_setup",
    correlation: CorrelationContext | None = None,
    idempotency_key: str = "setup-key",
    request_hash_payload: dict | None = None,
    max_chunks: int | None = 1,
) -> CharacterPersonaSetupWorkflowRequest:
    provider = provider or SetupWorkflowProvider()
    return CharacterPersonaSetupWorkflowRequest(
        source_work_id=source_work_id,
        character_id=character_id,
        provider_roles=PersonaSetupProviderRoleBundle(
            reader=provider,
            verifier=provider,
            persona_compiler=provider,
        ),
        model_roles=PersonaSetupModelRoleBundle(
            reader=ModelConfig(model="reader-model"),
            verifier=ModelConfig(model="verifier-model"),
            persona_compiler=ModelConfig(model="compiler-model"),
        ),
        actor=_actor(),
        correlation=correlation or CorrelationContext(request_id="req_setup"),
        idempotency=build_idempotency_context(
            workflow_type=CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
            idempotency_key=idempotency_key,
            request_payload=request_hash_payload
            or {
                "source_work_id": source_work_id,
                "character_id": character_id,
                "workflow_options": {"max_chunks": max_chunks},
            },
        ),
        max_chunks=max_chunks,
        metadata={"client_label": "workflow-test"},
    )


def _actor() -> LocalActorContext:
    return LocalActorContext(
        actor_type="api_user",
        actor_id="api-local:test",
        actor_label="Local API test",
        user_id="user_001",
        operation_reason="set up character persona for test",
        metadata={"entrypoint": "test"},
    )


def _first_chunk_id(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            return line.strip("[]")
    raise AssertionError("reader prompt did not include a chunk id")


def _claim_ids_from_prompt(content: str) -> list[str]:
    claim_ids = [
        line.split(": ", 1)[1]
        for line in content.splitlines()
        if line.startswith("claim_id: ")
    ]
    if len(claim_ids) != 2:
        raise AssertionError(f"expected two claim ids, got {claim_ids!r}")
    return claim_ids


def _link_set(links) -> set[tuple[str, str, str]]:
    return {(link.entity_type, link.entity_id, link.relation) for link in links}


def _counts(session) -> dict[str, int]:
    return {
        "claims": len(CanonClaimRepository(session).list_all()),
        "evidence": len(EvidenceRefRepository(session).list_all()),
        "conflicts": len(ClaimConflictRepository(session).list_all()),
        "personas": len(PersonaVersionRepository(session).list_all()),
        "traces": len(LLMRawOutputRepository(session).list_all()),
        "audits": len(AuditEventRepository(session).list_all()),
        "workflows": len(WorkflowRunRepository(session).list_all()),
        "idempotency_records": len(IdempotencyRecordRepository(session).list_all()),
    }


def _serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
