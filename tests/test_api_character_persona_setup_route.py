from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.api.routes import characters as character_routes
from personality_jelly.application import (
    CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE,
    create_database_resources,
)
from personality_jelly.core import Settings
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.storage import (
    AuditEventRepository,
    CanonClaimRepository,
    ClaimConflictRepository,
    EvidenceRefRepository,
    IdempotencyRecordRepository,
    LLMRawOutputRepository,
    PersonaVersionRepository,
    WorkflowRunRepository,
)


@dataclass
class SetupRouteProvider:
    name: str = "setup-route-provider"
    schema_titles: list[str] | None = None
    model_names: list[str] | None = None

    def __post_init__(self) -> None:
        if self.schema_titles is None:
            self.schema_titles = []
        if self.model_names is None:
            self.model_names = []

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        self.schema_titles.append(schema_title)
        self.model_names.append(model_config.model)
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


class ExplodingProvider(SetupRouteProvider):
    def generate_json(self, messages, schema, model_config):
        raise AssertionError("provider should not be called during replay or conflict")


class TransportFailureProvider(SetupRouteProvider):
    def __init__(self, fail_schema_title: str) -> None:
        super().__init__()
        self.fail_schema_title = fail_schema_title

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        if schema_title == self.fail_schema_title:
            self.schema_titles.append(schema_title)
            self.model_names.append(model_config.model)
            raise RuntimeError(
                "provider transport failed with api_key=sk-raw-secret "
                r"and path C:\Users\figna\provider.log"
            )
        return super().generate_json(messages, schema, model_config)


class ValidationFailureProvider(SetupRouteProvider):
    def __init__(self, fail_schema_title: str) -> None:
        super().__init__()
        self.fail_schema_title = fail_schema_title

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        if schema_title == self.fail_schema_title:
            self.schema_titles.append(schema_title)
            self.model_names.append(model_config.model)
            return {
                "raw_provider_output": "RAW_PROVIDER_OUTPUT_SHOULD_NOT_LEAK",
                "source_text": "Lin Shuang observes before acting.",
                "claims": "not-a-list",
                "decisions": "not-a-list",
                "core_self": 123,
            }
        return super().generate_json(messages, schema, model_config)


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_post_persona_setup_after_source_and_character_creates_safe_response_and_diagnostics(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = SetupRouteProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_setup_api",
            character_id="char_setup_api",
        )
        response = client.post(
            "/characters/char_setup_api/persona-setup-runs",
            headers={
                "X-Request-ID": "req_setup_api",
                "Idempotency-Key": "setup-create-key",
            },
            json=_setup_body(source_work_id="sw_setup_api"),
        )
        payload = response.json()
        workflow_response = client.get(f"/workflow-runs/{payload['workflow_id']}")
        audit_response = client.get(f"/audit-events/{payload['ids']['audit_event_id']}")

    assert response.status_code == 201
    assert payload["request_id"] == "req_setup_api"
    assert payload["workflow_type"] == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert payload["status"] == "completed"
    assert payload["ids"]["source_work_id"] == "sw_setup_api"
    assert payload["ids"]["character_id"] == "char_setup_api"
    assert payload["ids"]["persona_version_id"].startswith("pv_")
    assert len(payload["ids"]["llm_trace_ids"]) == 3
    assert payload["ids"]["audit_event_id"].startswith("audit_")
    assert payload["result"]["persisted_ids"]["source_work_id"] == "sw_setup_api"
    assert payload["result"]["persisted_ids"]["character_id"] == "char_setup_api"
    assert len(payload["result"]["persisted_ids"]["candidate_claim_ids"]) == 2
    assert len(payload["result"]["persisted_ids"]["evidence_ref_ids"]) == 2
    assert len(payload["result"]["persisted_ids"]["verified_claim_ids"]) == 1
    assert len(payload["result"]["persisted_ids"]["conflict_ids"]) == 1
    assert payload["result"]["counts"] == {
        "candidate_claims": 2,
        "evidence_refs": 2,
        "verified_claims": 1,
        "conflicts": 1,
        "llm_traces": 3,
        "audit_events": 1,
    }
    assert payload["result"]["redaction"]["source_text_redacted"] is True
    assert payload["result"]["redaction"]["prompts_redacted"] is True
    assert provider.schema_titles == [
        "ReaderExtraction",
        "VerifierResult",
        "PersonaCompilation",
    ]
    assert provider.model_names == [
        "reader-route-model",
        "verifier-route-model",
        "compiler-route-model",
    ]
    assert "Lin Shuang observes before acting." not in response.text
    assert "Lin Shuang is cautious and observant." not in response.text
    assert "raw_provider_output" not in response.text

    assert workflow_response.status_code == 200
    workflow = workflow_response.json()
    assert workflow["workflow_type"] == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert workflow["status"] == "completed"
    assert workflow["persisted_ids"]["persona_version_id"] == payload["ids"][
        "persona_version_id"
    ]
    assert "Lin Shuang observes before acting." not in workflow_response.text

    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["operation"] == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    assert audit["status"] == "succeeded"
    assert audit["entity_type"] == "character"
    assert audit["entity_id"] == "char_setup_api"
    assert audit["after"]["counts"]["verified_claims"] == 1
    assert "Lin Shuang observes before acting." not in audit_response.text


def test_post_persona_setup_generates_request_id_when_omitted(tmp_path, monkeypatch) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    monkeypatch.setattr(character_routes, "StubProvider", lambda: SetupRouteProvider())

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_generated",
            character_id="char_generated",
        )
        response = client.post(
            "/characters/char_generated/persona-setup-runs",
            headers={"Idempotency-Key": "setup-generated-key"},
            json=_setup_body(source_work_id="sw_generated"),
        )

    assert response.status_code == 201
    assert response.json()["request_id"].startswith("req_")


def test_post_persona_setup_requires_idempotency_key(tmp_path, monkeypatch) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = SetupRouteProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_missing_key",
            character_id="char_missing_key",
        )
        response = client.post(
            "/characters/char_missing_key/persona-setup-runs",
            json=_setup_body(source_work_id="sw_missing_key"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "Idempotency-Key is required"
    assert provider.schema_titles == []
    assert _setup_counts(resources)["setup_workflows"] == 0


def test_post_persona_setup_validates_idempotency_header_and_body_match(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = SetupRouteProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_key_mismatch",
            character_id="char_key_mismatch",
        )
        matched = client.post(
            "/characters/char_key_mismatch/persona-setup-runs",
            headers={"Idempotency-Key": "matching-key"},
            json={
                **_setup_body(source_work_id="sw_key_mismatch"),
                "idempotency_key": "matching-key",
            },
        )
        mismatched = client.post(
            "/characters/char_key_mismatch/persona-setup-runs",
            headers={"Idempotency-Key": "header-key"},
            json={
                **_setup_body(source_work_id="sw_key_mismatch"),
                "idempotency_key": "body-key",
            },
        )

    assert matched.status_code == 201
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "validation_error"
    assert (
        mismatched.json()["error"]["message"]
        == "Idempotency-Key and body idempotency_key must match"
    )


def test_post_persona_setup_replays_without_provider_calls_or_duplicate_rows(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    first_provider = SetupRouteProvider()
    exploding_provider = ExplodingProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: first_provider)

    with TestClient(app) as client:
        _seed_source_and_character(client, source_work_id="sw_replay", character_id="char_replay")
        first = client.post(
            "/characters/char_replay/persona-setup-runs",
            headers={"Idempotency-Key": "setup-replay-key"},
            json={**_setup_body(source_work_id="sw_replay"), "request_id": "req_setup_first"},
        )
        counts_after_first = _setup_counts(resources)
        monkeypatch.setattr(character_routes, "StubProvider", lambda: exploding_provider)
        second = client.post(
            "/characters/char_replay/persona-setup-runs",
            headers={"Idempotency-Key": "setup-replay-key"},
            json={**_setup_body(source_work_id="sw_replay"), "request_id": "req_setup_second"},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert first.json()["request_id"] == "req_setup_first"
    assert counts_after_first == _setup_counts(resources)
    assert exploding_provider.schema_titles == []


def test_post_persona_setup_rejects_same_key_different_body_without_provider_calls(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    first_provider = SetupRouteProvider()
    exploding_provider = ExplodingProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: first_provider)

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_conflict",
            character_id="char_conflict",
        )
        first = client.post(
            "/characters/char_conflict/persona-setup-runs",
            headers={"Idempotency-Key": "setup-conflict-key"},
            json=_setup_body(source_work_id="sw_conflict", metadata={"client_label": "first"}),
        )
        counts_after_first = _setup_counts(resources)
        monkeypatch.setattr(character_routes, "StubProvider", lambda: exploding_provider)
        second = client.post(
            "/characters/char_conflict/persona-setup-runs",
            headers={"Idempotency-Key": "setup-conflict-key"},
            json=_setup_body(source_work_id="sw_conflict", metadata={"client_label": "second"}),
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"
    assert (
        second.json()["error"]["details"]["workflow_type"]
        == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
    )
    assert second.json()["error"]["details"]["conflict"] == "request_hash_mismatch"
    assert "second" not in second.text
    assert "setup-conflict-key" not in second.text
    assert counts_after_first == _setup_counts(resources)
    assert exploding_provider.schema_titles == []


def test_post_persona_setup_returns_not_found_for_missing_source_or_character(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = SetupRouteProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(client, source_work_id="sw_exists", character_id="char_exists")
        missing_source = client.post(
            "/characters/char_exists/persona-setup-runs",
            headers={"Idempotency-Key": "missing-source-key"},
            json=_setup_body(source_work_id="missing_source"),
        )
        missing_character = client.post(
            "/characters/missing_character/persona-setup-runs",
            headers={"Idempotency-Key": "missing-character-key"},
            json=_setup_body(source_work_id="sw_exists"),
        )

    for response in (missing_source, missing_character):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert provider.schema_titles == []
    assert _setup_counts(resources)["setup_workflows"] == 0


def test_post_persona_setup_rejects_source_character_mismatch(tmp_path, monkeypatch) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = SetupRouteProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _post_source(client, source_work_id="sw_primary")
        _post_character(client, source_work_id="sw_primary", character_id="char_primary")
        _post_source(client, source_work_id="sw_other")
        response = client.post(
            "/characters/char_primary/persona-setup-runs",
            headers={"Idempotency-Key": "source-mismatch-key"},
            json=_setup_body(source_work_id="sw_other"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "does not belong to source work" in response.json()["error"]["message"]
    assert provider.schema_titles == []
    assert _setup_counts(resources)["setup_workflows"] == 0


def test_post_persona_setup_provider_failure_before_business_rows_is_sanitized_502(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = TransportFailureProvider("ReaderExtraction")
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(
            client,
            source_work_id="sw_provider_fail",
            character_id="char_provider_fail",
        )
        response = client.post(
            "/characters/char_provider_fail/persona-setup-runs",
            headers={"Idempotency-Key": "provider-failure-key"},
            json=_setup_body(source_work_id="sw_provider_fail"),
        )

    payload = response.json()
    assert response.status_code == 502
    assert payload["error"]["code"] == "provider_failure"
    assert payload["error"]["details"]["failed_step"] == "reader_extract"
    assert "candidate_claim_ids" not in payload["error"]["details"]["persisted_ids"]
    assert payload["error"]["details"]["details"]["counts"]["candidate_claims"] == 0
    assert "sk-raw-secret" not in response.text
    assert "C:\\Users" not in response.text
    assert "provider.log" not in response.text
    assert _setup_counts(resources) == {
        "claims": 0,
        "evidence": 0,
        "conflicts": 0,
        "personas": 0,
        "traces": 0,
        "setup_audits": 1,
        "setup_workflows": 1,
        "setup_idempotency_records": 1,
    }


def test_post_persona_setup_partial_after_staged_rows_is_sanitized_500(
    tmp_path,
    monkeypatch,
) -> None:
    resources = _resources(tmp_path)
    app = create_app(settings=_settings(), database_resources=resources)
    provider = ValidationFailureProvider("VerifierResult")
    exploding_provider = ExplodingProvider()
    monkeypatch.setattr(character_routes, "StubProvider", lambda: provider)

    with TestClient(app) as client:
        _seed_source_and_character(client, source_work_id="sw_partial", character_id="char_partial")
        response = client.post(
            "/characters/char_partial/persona-setup-runs",
            headers={"Idempotency-Key": "partial-key"},
            json=_setup_body(source_work_id="sw_partial"),
        )
        counts_after_first = _setup_counts(resources)
        monkeypatch.setattr(character_routes, "StubProvider", lambda: exploding_provider)
        replay = client.post(
            "/characters/char_partial/persona-setup-runs",
            headers={"Idempotency-Key": "partial-key"},
            json={**_setup_body(source_work_id="sw_partial"), "request_id": "req_partial_replay"},
        )

    payload = response.json()
    assert response.status_code == 500
    assert payload["error"]["code"] == "partial_persistence"
    assert payload["error"]["details"]["error_code"] == "provider_validation_error"
    assert payload["error"]["details"]["failed_step"] == "verifier_validate"
    assert payload["error"]["details"]["persisted_ids"]["candidate_claim_ids"]
    assert payload["error"]["details"]["persisted_ids"]["evidence_ref_ids"]
    assert payload["error"]["details"]["retry_hint"]
    assert "RAW_PROVIDER_OUTPUT_SHOULD_NOT_LEAK" not in response.text
    assert "Lin Shuang observes before acting." not in response.text
    expected_counts = {
        "claims": 2,
        "evidence": 2,
        "conflicts": 0,
        "personas": 0,
        "traces": 2,
        "setup_audits": 1,
        "setup_workflows": 1,
        "setup_idempotency_records": 1,
    }
    assert counts_after_first == expected_counts
    assert _setup_counts(resources) == expected_counts
    assert replay.status_code == 500
    assert replay.json() == payload
    assert exploding_provider.schema_titles == []


def test_openapi_persona_setup_schema_exposes_only_safe_fields(tmp_path) -> None:
    app = create_app(
        settings=_settings(),
        database_url=f"sqlite:///{tmp_path / 'api-persona-setup-openapi.db'}",
    )

    openapi = app.openapi()
    operation = openapi["paths"]["/characters/{character_id}/persona-setup-runs"]["post"]
    request_schema_ref = operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    response_schema_ref = operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"]

    request_properties = _collect_schema_properties(openapi, request_schema_ref)
    response_properties = _collect_schema_properties(openapi, response_schema_ref)

    assert {
        "source_work_id",
        "provider",
        "workflow_options",
        "actor",
        "request_id",
        "idempotency_key",
        "metadata",
        "source",
        "model",
        "roles",
        "reader",
        "verifier",
        "persona_compiler",
        "max_chunks",
    }.issubset(request_properties)
    assert {
        "request_id",
        "workflow_id",
        "workflow_type",
        "status",
        "ids",
        "result",
        "persisted_ids",
        "counts",
        "redaction",
        "source_text_redacted",
        "prompts_redacted",
        "provider_payloads_redacted",
        "provider_config_redacted",
        "raw_outputs_redacted",
    }.issubset(response_properties)

    forbidden_request_fields = {
        "api_key",
        "authorization",
        "base_url",
        "headers",
        "prompt",
        "provider_config",
        "provider_payload",
        "source_text",
        "raw_output",
        "path",
        "local_path",
        "file_path",
        "url",
        "content",
    }
    forbidden_response_fields = {
        "api_key",
        "authorization",
        "base_url",
        "headers",
        "prompt",
        "provider_config",
        "provider_payload",
        "source_text",
        "chunk_text",
        "evidence_excerpt",
        "raw_output",
        "parsed_output",
        "response_schema",
        "validation_errors",
        "core_self",
        "speech_rules",
        "behavior_rules",
        "path",
        "local_path",
        "file_path",
        "url",
        "content",
    }
    assert forbidden_request_fields.isdisjoint(request_properties)
    assert forbidden_response_fields.isdisjoint(response_properties)


def _resources(tmp_path):
    return create_database_resources(f"sqlite:///{tmp_path / 'api-persona-setup.db'}")


def _seed_source_and_character(
    client: TestClient,
    *,
    source_work_id: str,
    character_id: str,
) -> None:
    source = _post_source(client, source_work_id=source_work_id)
    assert source.status_code == 201
    character = _post_character(
        client,
        source_work_id=source_work_id,
        character_id=character_id,
    )
    assert character.status_code == 201


def _post_source(client: TestClient, *, source_work_id: str):
    return client.post(
        "/source-works",
        headers={"Idempotency-Key": f"source-key-{source_work_id}"},
        json=_source_body(source_work_id=source_work_id),
    )


def _post_character(
    client: TestClient,
    *,
    source_work_id: str,
    character_id: str,
):
    return client.post(
        "/characters",
        json=_character_body(source_work_id=source_work_id, character_id=character_id),
    )


def _source_body(*, source_work_id: str) -> dict[str, Any]:
    return {
        "source_work_id": source_work_id,
        "title": "Inline Source",
        "author": "Author",
        "language": "zh-CN",
        "source_type": "markdown",
        "content": "# Chapter\n\nLin Shuang observes before acting.\n\nThen she waits.",
        "content_encoding": "utf-8",
        "chunking": {"max_paragraph_chars": 500, "min_paragraph_chars": 1},
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "ingest source for persona setup route test",
            "metadata": {"entrypoint": "test"},
        },
        "metadata": {"client_label": "persona-setup-route-test"},
    }


def _character_body(*, source_work_id: str, character_id: str) -> dict[str, Any]:
    return {
        "source_work_id": source_work_id,
        "character_id": character_id,
        "canonical_name": "Lin Shuang",
        "aliases": ["A Shuang"],
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "create character for persona setup route test",
            "metadata": {"entrypoint": "test"},
        },
        "metadata": {"client_label": "persona-setup-route-test"},
    }


def _setup_body(
    *,
    source_work_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_work_id": source_work_id,
        "provider": {
            "source": "stub",
            "model": "setup-route-model",
            "roles": {
                "reader": {"model": "reader-route-model"},
                "verifier": {"model": "verifier-route-model"},
                "persona_compiler": {"model": "compiler-route-model"},
            },
        },
        "workflow_options": {"max_chunks": 1},
        "actor": {
            "actor_id": "api-local:test",
            "actor_label": "Local API test",
            "user_id": "user_001",
            "operation_reason": "set up character persona for route test",
            "metadata": {"entrypoint": "test"},
        },
        "metadata": metadata or {"client_label": "persona-setup-route-test"},
    }


def _setup_counts(resources) -> dict[str, int]:
    with resources.session_factory() as session:
        setup_workflows = [
            workflow
            for workflow in WorkflowRunRepository(session).list_all()
            if workflow.workflow_type == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
        ]
        setup_records = [
            record
            for record in IdempotencyRecordRepository(session).list_all()
            if record.workflow_type == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
        ]
        setup_audits = [
            event
            for event in AuditEventRepository(session).list_all()
            if event.operation == CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE
        ]
        return {
            "claims": len(CanonClaimRepository(session).list_all()),
            "evidence": len(EvidenceRefRepository(session).list_all()),
            "conflicts": len(ClaimConflictRepository(session).list_all()),
            "personas": len(PersonaVersionRepository(session).list_all()),
            "traces": len(LLMRawOutputRepository(session).list_all()),
            "setup_audits": len(setup_audits),
            "setup_workflows": len(setup_workflows),
            "setup_idempotency_records": len(setup_records),
        }


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


def _collect_schema_properties(
    openapi: dict[str, Any],
    schema_or_ref: str | dict[str, Any],
    seen: set[str] | None = None,
) -> set[str]:
    seen = seen or set()
    if isinstance(schema_or_ref, str):
        ref_name = schema_or_ref.rsplit("/", 1)[-1]
        if ref_name in seen:
            return set()
        seen.add(ref_name)
        schema = openapi["components"]["schemas"][ref_name]
    else:
        schema = schema_or_ref

    properties = set(schema.get("properties", {}))
    for value in schema.get("properties", {}).values():
        properties.update(_collect_schema_child_properties(openapi, value, seen))
    for key in ("anyOf", "oneOf", "allOf"):
        for item in schema.get(key, []):
            properties.update(_collect_schema_child_properties(openapi, item, seen))
    if "items" in schema:
        properties.update(_collect_schema_child_properties(openapi, schema["items"], seen))
    return properties


def _collect_schema_child_properties(
    openapi: dict[str, Any],
    schema: dict[str, Any],
    seen: set[str],
) -> set[str]:
    if "$ref" in schema:
        return _collect_schema_properties(openapi, schema["$ref"], seen)
    return _collect_schema_properties(openapi, schema, seen)
