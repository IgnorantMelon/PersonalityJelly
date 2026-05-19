import pytest

from personality_jelly.characters import create_character
from personality_jelly.domain import SourceWork
from personality_jelly.storage import (
    CharacterRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    return create_session_factory(engine)


def test_create_character_persists_normalized_name_and_aliases() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="测试作品", source_type="markdown")
        )
        result = create_character(
            session,
            source_work_id="sw_001",
            canonical_name="  林   霜  ",
            aliases=["阿霜", " 林 霜 ", "", "阿霜"],
            character_id="char_001",
        )
        session.commit()

    with session_factory() as session:
        stored = CharacterRepository(session).require("char_001")

    assert result.character.id == "char_001"
    assert stored.canonical_name == "林 霜"
    assert stored.aliases == ["阿霜"]


def test_create_character_requires_existing_source_work() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        with pytest.raises(LookupError):
            create_character(session, source_work_id="missing", canonical_name="林霜")


def test_create_character_rejects_duplicate_name_in_same_source_work() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="测试作品", source_type="markdown")
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="林霜",
            character_id="char_001",
        )

        with pytest.raises(ValueError, match="already exists"):
            create_character(
                session,
                source_work_id="sw_001",
                canonical_name="林霜",
                character_id="char_002",
            )

