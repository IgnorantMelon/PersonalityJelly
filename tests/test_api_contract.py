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
        "/conversations": {"get"},
        "/conversations/{conversation_id}": {"get"},
        "/context-packages/{context_package_id}": {"get"},
        "/characters": {"get"},
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
            assert "200" in operation["responses"], path
            assert "application/json" in operation["responses"]["200"]["content"], path


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
