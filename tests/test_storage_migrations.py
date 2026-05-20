from sqlalchemy import inspect

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
    assert [migration.version for migration in result.applied] == [CURRENT_SCHEMA_VERSION]
    assert "schema_migrations" in table_names
    assert "source_works" in table_names
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()


def test_migrate_database_is_idempotent() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    first = migrate_database(engine)
    second = migrate_database(engine)

    assert len(first.applied) == 1
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
    assert [migration.version for migration in result.applied] == [CURRENT_SCHEMA_VERSION]
    assert result.status.current_version == CURRENT_SCHEMA_VERSION
    assert result.status.pending == ()
