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

    expected_paths = {
        "/health",
        "/conversations",
        "/conversations/{conversation_id}",
        "/context-packages/{context_package_id}",
        "/characters",
        "/characters/{character_id}",
        "/claims",
        "/claims/{claim_id}",
        "/memories",
        "/memories/{memory_id}",
        "/source-chunks/{chunk_id}",
        "/critic-reports/{critic_report_id}",
        "/failure-cases",
        "/failure-cases/{failure_case_id}",
        "/llm-traces",
        "/llm-traces/{trace_id}",
        "/eval-runs",
        "/eval-runs/{run_id}",
        "/retrieval-eval-runs",
        "/retrieval-eval-runs/{run_id}",
    }
    assert set(paths) == expected_paths

    for path, path_item in paths.items():
        expected_methods = {"get", "post"} if path == "/conversations" else {"get"}
        assert set(path_item) == expected_methods, path
        operation = path_item["get"]
        assert "200" in operation["responses"], path
        assert "application/json" in operation["responses"]["200"]["content"], path

    conversation_create = paths["/conversations"]["post"]
    assert conversation_create["tags"] == ["conversation-context"]
    assert "201" in conversation_create["responses"]
    assert "application/json" in conversation_create["responses"]["201"]["content"]


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
