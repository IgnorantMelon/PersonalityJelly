from __future__ import annotations

from personality_jelly.api import create_app
from personality_jelly.core import Settings


def _settings(**values) -> Settings:
    return Settings(config_file="missing-test-pjelly.toml", _env_file=None, **values)


def test_openapi_contract_exposes_expected_route_set(tmp_path) -> None:
    app = create_app(
        settings=_settings(),
        database_url=f"sqlite:///{tmp_path / 'api-contract.db'}",
    )

    openapi = app.openapi()
    paths = openapi["paths"]

    expected_path_methods = {
        "/health": {"get"},
        "/source-works": {"post"},
        "/conversations": {"get", "post"},
        "/conversations/{conversation_id}": {"get"},
        "/context-packages/{context_package_id}": {"get"},
        "/characters": {"get", "post"},
        "/characters/{character_id}": {"get"},
        "/claims": {"get"},
        "/claims/{claim_id}": {"get"},
        "/memories": {"get"},
        "/memories/{memory_id}": {"get", "patch"},
        "/memories/{memory_id}/review": {"post"},
        "/memories/{memory_id}/archive": {"post"},
        "/source-chunks/{chunk_id}": {"get"},
        "/critic-reports/{critic_report_id}": {"get"},
        "/failure-cases": {"get"},
        "/failure-cases/{failure_case_id}": {"get"},
        "/llm-traces": {"get"},
        "/llm-traces/{trace_id}": {"get"},
        "/audit-events": {"get"},
        "/audit-events/{audit_event_id}": {"get"},
        "/workflow-runs": {"get"},
        "/workflow-runs/{workflow_id}": {"get"},
        "/eval-runs": {"get"},
        "/eval-runs/{run_id}": {"get"},
        "/retrieval-eval-runs": {"get"},
        "/retrieval-eval-runs/{run_id}": {"get"},
    }
    assert set(paths) == set(expected_path_methods)

    for path, path_item in paths.items():
        assert set(path_item) == expected_path_methods[path], path
        for method in expected_path_methods[path]:
            operation = path_item[method]
            expected_status = (
                "201"
                if path in {"/conversations", "/source-works", "/characters"}
                and method == "post"
                else "200"
            )
            assert expected_status in operation["responses"], path
            assert (
                "application/json"
                in operation["responses"][expected_status]["content"]
            ), path

    conversation_create = paths["/conversations"]["post"]
    assert conversation_create["tags"] == ["conversation-context"]
    assert "201" in conversation_create["responses"]
    assert "application/json" in conversation_create["responses"]["201"]["content"]

    source_create = paths["/source-works"]["post"]
    assert source_create["tags"] == ["sources"]
    assert "201" in source_create["responses"]
    assert "application/json" in source_create["responses"]["201"]["content"]

    character_create = paths["/characters"]["post"]
    assert character_create["tags"] == ["characters"]
    assert "201" in character_create["responses"]
    assert "application/json" in character_create["responses"]["201"]["content"]


def test_openapi_contract_keeps_route_tags_and_query_params_stable(tmp_path) -> None:
    app = create_app(
        settings=_settings(),
        database_url=f"sqlite:///{tmp_path / 'api-contract.db'}",
    )

    paths = app.openapi()["paths"]
    expected = {
        "/health": ("health", []),
        "/conversations": ("conversation-context", ["limit"]),
        "/conversations/{conversation_id}": (
            "conversation-context",
            [
                "message_limit",
                "include_user",
                "include_character",
                "include_persona_version",
                "include_memories",
            ],
        ),
        "/context-packages/{context_package_id}": (
            "conversation-context",
            [
                "include_persona_version",
                "include_claims",
                "include_evidence",
                "include_evidence_chunks",
                "include_memories",
                "include_retrieved_chunks",
                "include_retrieved_chunk_text",
            ],
        ),
        "/characters": ("characters", ["source_work_id"]),
        "/characters/{character_id}": ("characters", []),
        "/claims": ("characters", ["character_id", "status", "claim_type"]),
        "/claims/{claim_id}": ("characters", []),
        "/memories": ("characters", ["user_id", "character_id", "scope", "status"]),
        "/memories/{memory_id}": ("characters", []),
        "/source-chunks/{chunk_id}": ("characters", []),
        "/critic-reports/{critic_report_id}": ("diagnostics", []),
        "/failure-cases": ("diagnostics", ["conversation_id", "category", "limit"]),
        "/failure-cases/{failure_case_id}": ("diagnostics", []),
        "/llm-traces": (
            "diagnostics",
            [
                "operation",
                "schema_name",
                "provider_name",
                "model_name",
                "with_errors",
                "limit",
            ],
        ),
        "/llm-traces/{trace_id}": ("diagnostics", []),
        "/audit-events": (
            "diagnostics",
            [
                "request_id",
                "workflow_id",
                "workflow_type",
                "operation",
                "actor_id",
                "entity_type",
                "entity_id",
                "status",
                "user_id",
                "character_id",
                "conversation_id",
                "limit",
            ],
        ),
        "/audit-events/{audit_event_id}": ("diagnostics", []),
        "/workflow-runs": (
            "diagnostics",
            [
                "request_id",
                "workflow_id",
                "workflow_type",
                "status",
                "user_id",
                "character_id",
                "conversation_id",
                "limit",
            ],
        ),
        "/workflow-runs/{workflow_id}": ("diagnostics", []),
        "/eval-runs": ("diagnostics", ["character_id", "test_suite", "limit"]),
        "/eval-runs/{run_id}": ("diagnostics", ["failed_only"]),
        "/retrieval-eval-runs": (
            "diagnostics",
            ["character_id", "source_work_id", "test_suite", "limit"],
        ),
        "/retrieval-eval-runs/{run_id}": (
            "diagnostics",
            ["failed_only", "include_chunks"],
        ),
    }

    for path, (tag, query_params) in expected.items():
        operation = paths[path]["get"]
        assert operation["tags"] == [tag]
        actual_query_params = [
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter["in"] == "query"
        ]
        assert actual_query_params == query_params


def test_openapi_source_ingest_schema_excludes_deferred_and_sensitive_fields(tmp_path) -> None:
    app = create_app(
        settings=_settings(),
        database_url=f"sqlite:///{tmp_path / 'api-contract.db'}",
    )

    openapi = app.openapi()
    source_operation = openapi["paths"]["/source-works"]["post"]
    request_schema_ref = source_operation["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    response_schema_ref = source_operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"]

    request_schema_name = request_schema_ref.rsplit("/", 1)[-1]
    response_schema_name = response_schema_ref.rsplit("/", 1)[-1]
    request_schema = openapi["components"]["schemas"][request_schema_name]
    response_schema = openapi["components"]["schemas"][response_schema_name]
    schema_text = str(request_schema) + str(response_schema)

    request_properties = set(request_schema["properties"])
    assert {
        "title",
        "source_type",
        "content",
        "actor",
        "request_id",
        "idempotency_key",
        "source_work_id",
        "author",
        "language",
        "content_encoding",
        "chunking",
        "metadata",
    }.issubset(request_properties)

    forbidden_fragments = [
        "local_path",
        "file_path",
        "'path'",
        "'uri'",
        "remote_url",
        "multipart",
        "upload",
        "base64",
        "binary",
        "provider_config",
        "llm_config",
        "embedding_config",
        "prompt",
        "raw_output",
        "debug",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in schema_text

    response_properties = set(response_schema["properties"])
    assert {"request_id", "workflow_id", "workflow_type", "status", "ids", "result"}.issubset(
        response_properties
    )
    result_ref = response_schema["properties"]["result"]["$ref"]
    result_schema = openapi["components"]["schemas"][result_ref.rsplit("/", 1)[-1]]
    result_properties = set(result_schema["properties"])
    assert {
        "source_work",
        "persisted_ids",
        "chunk_count",
        "chunk_ids",
        "first_chunk_id",
        "last_chunk_id",
        "text_redacted",
        "source_preview_redacted",
    }.issubset(result_properties)
    assert "content" not in result_properties


def test_openapi_character_create_schema_excludes_persona_setup_and_sensitive_fields(
    tmp_path,
) -> None:
    app = create_app(
        settings=_settings(),
        database_url=f"sqlite:///{tmp_path / 'api-contract.db'}",
    )

    openapi = app.openapi()
    character_operation = openapi["paths"]["/characters"]["post"]
    request_schema_ref = character_operation["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    response_schema_ref = character_operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"]

    request_schema_name = request_schema_ref.rsplit("/", 1)[-1]
    response_schema_name = response_schema_ref.rsplit("/", 1)[-1]
    request_schema = openapi["components"]["schemas"][request_schema_name]
    response_schema = openapi["components"]["schemas"][response_schema_name]
    schema_text = str(request_schema) + str(response_schema)

    request_properties = set(request_schema["properties"])
    assert {
        "source_work_id",
        "canonical_name",
        "actor",
        "request_id",
        "idempotency_key",
        "aliases",
        "character_id",
        "metadata",
    }.issubset(request_properties)

    forbidden_fragments = [
        "persona_setup",
        "setup_runs",
        "workflow_options",
        "provider",
        "provider_config",
        "llm_config",
        "embedding_config",
        "prompt",
        "raw_output",
        "source_text",
        "chunk_text",
        "file_path",
        "local_path",
        "debug",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in schema_text

    response_properties = set(response_schema["properties"])
    assert {"request_id", "workflow_id", "workflow_type", "status", "ids", "result"}.issubset(
        response_properties
    )
    result_ref = response_schema["properties"]["result"]["$ref"]
    result_schema = openapi["components"]["schemas"][result_ref.rsplit("/", 1)[-1]]
    result_properties = set(result_schema["properties"])
    assert {"character", "audit_event"}.issubset(result_properties)
    assert "text" not in result_properties
    assert "source_text" not in result_properties
