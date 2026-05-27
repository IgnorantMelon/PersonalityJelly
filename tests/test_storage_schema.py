from sqlalchemy import inspect

from personality_jelly.storage import create_all, create_database_engine


def test_create_all_creates_mvp_tables() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    create_all(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "source_works",
        "source_chunks",
        "source_chunk_embeddings",
        "characters",
        "canon_claims",
        "evidence_refs",
        "claim_conflicts",
        "persona_versions",
        "users",
        "conversations",
        "messages",
        "memories",
        "context_packages",
        "critic_reports",
        "failure_cases",
        "llm_raw_outputs",
        "workflow_runs",
        "workflow_run_links",
        "idempotency_records",
        "evaluation_runs",
        "evaluation_case_results",
        "retrieval_evaluation_runs",
        "retrieval_evaluation_case_results",
        "audit_events",
    } <= table_names

    llm_columns = {column["name"] for column in inspect(engine).get_columns("llm_raw_outputs")}
    assert {"request_id", "workflow_id", "workflow_step", "related_ids"} <= llm_columns

    idempotency_columns = {
        column["name"] for column in inspect(engine).get_columns("idempotency_records")
    }
    assert {
        "workflow_type",
        "idempotency_key",
        "request_hash",
        "request_id",
        "workflow_id",
        "response_status_code",
        "replay_payload",
        "related_ids",
    } <= idempotency_columns

