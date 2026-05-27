from datetime import datetime, timezone

from sqlalchemy import inspect, text

from personality_jelly.storage import (
    CURRENT_SCHEMA_VERSION,
    create_all,
    create_database_engine,
    get_migration_status,
    migrate_database,
)


def test_migrate_database_initializes_empty_database_and_records_version() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    result = migrate_database(engine)
    table_names = set(inspect(engine).get_table_names())

    assert result.baselined_existing_database is False
    assert [migration.version for migration in result.applied] == [
        "0001_initial_schema",
        "0002_source_chunk_embeddings",
        "0003_retrieval_evaluation",
        CURRENT_SCHEMA_VERSION,
    ]
    assert "schema_migrations" in table_names
    assert "source_works" in table_names
    assert "source_chunk_embeddings" in table_names
    assert "audit_events" in table_names
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()


def test_migrate_database_is_idempotent() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    first = migrate_database(engine)
    second = migrate_database(engine)

    assert len(first.applied) == 4
    assert second.applied == ()
    assert second.status.current_version == CURRENT_SCHEMA_VERSION


def test_migrate_database_baselines_existing_create_all_database() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)

    initial_status = get_migration_status(engine)
    result = migrate_database(engine)

    assert initial_status.has_schema_migrations_table is False
    assert initial_status.has_application_tables is True
    assert result.baselined_existing_database is True
    assert [migration.version for migration in result.applied] == [
        "0001_initial_schema",
        "0002_source_chunk_embeddings",
        "0003_retrieval_evaluation",
        CURRENT_SCHEMA_VERSION,
    ]
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()


def test_migrate_database_applies_source_chunk_embedding_table_to_v1_database() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY, "
                "description VARCHAR(255) NOT NULL, "
                "applied_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO schema_migrations "
                "(version, description, applied_at) "
                "VALUES (:version, :description, :applied_at)"
            ),
            {
                "version": "0001_initial_schema",
                "description": "Create MVP relational schema",
                "applied_at": datetime.now(timezone.utc),
            },
        )
        connection.execute(text("DROP TABLE source_chunk_embeddings"))

    result = migrate_database(engine)
    table_names = set(inspect(engine).get_table_names())

    assert [migration.version for migration in result.applied] == [
        "0002_source_chunk_embeddings",
        "0003_retrieval_evaluation",
        CURRENT_SCHEMA_VERSION,
    ]
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()
    assert "source_chunk_embeddings" in table_names
    assert "audit_events" in table_names


def test_migrate_database_applies_retrieval_evaluation_tables_to_v2_database() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY, "
                "description VARCHAR(255) NOT NULL, "
                "applied_at DATETIME NOT NULL)"
            )
        )
        for version, description in [
            ("0001_initial_schema", "Create MVP relational schema"),
            ("0002_source_chunk_embeddings", "Persist source chunk embeddings"),
        ]:
            connection.execute(
                text(
                    "INSERT INTO schema_migrations "
                    "(version, description, applied_at) "
                    "VALUES (:version, :description, :applied_at)"
                ),
                {
                    "version": version,
                    "description": description,
                    "applied_at": datetime.now(timezone.utc),
                },
            )
        connection.execute(text("DROP TABLE retrieval_evaluation_case_results"))
        connection.execute(text("DROP TABLE retrieval_evaluation_runs"))

    result = migrate_database(engine)
    table_names = set(inspect(engine).get_table_names())

    assert [migration.version for migration in result.applied] == [
        "0003_retrieval_evaluation",
        CURRENT_SCHEMA_VERSION,
    ]
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()
    assert "retrieval_evaluation_runs" in table_names
    assert "retrieval_evaluation_case_results" in table_names
    assert "audit_events" in table_names


def test_migrate_database_applies_audit_events_table_to_v3_database() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY, "
                "description VARCHAR(255) NOT NULL, "
                "applied_at DATETIME NOT NULL)"
            )
        )
        for version, description in [
            ("0001_initial_schema", "Create MVP relational schema"),
            ("0002_source_chunk_embeddings", "Persist source chunk embeddings"),
            ("0003_retrieval_evaluation", "Persist retrieval quality evaluation runs"),
        ]:
            connection.execute(
                text(
                    "INSERT INTO schema_migrations "
                    "(version, description, applied_at) "
                    "VALUES (:version, :description, :applied_at)"
                ),
                {
                    "version": version,
                    "description": description,
                    "applied_at": datetime.now(timezone.utc),
                },
            )
        connection.execute(text("DROP TABLE audit_events"))

    result = migrate_database(engine)
    table_names = set(inspect(engine).get_table_names())
    indexes = {
        index["name"]
        for index in inspect(engine).get_indexes("audit_events")
    }

    assert [migration.version for migration in result.applied] == [CURRENT_SCHEMA_VERSION]
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()
    assert "audit_events" in table_names
    assert "ix_audit_events_operation_created" in indexes
    assert "ix_audit_events_memory_created" in indexes
