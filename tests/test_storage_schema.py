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
        "evaluation_runs",
        "evaluation_case_results",
    } <= table_names

