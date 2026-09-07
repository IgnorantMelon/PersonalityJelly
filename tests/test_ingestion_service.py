from pathlib import Path

from personality_jelly.ingestion import ingest_text_file
from personality_jelly.storage import (
    SourceChunkRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


def test_ingest_text_file_persists_source_work_and_chunks(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n第一段。\n\n第二段。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = ingest_text_file(
            session,
            source_file,
            title="样本文本",
            author="作者",
        )
        session.commit()

    with session_factory() as session:
        stored_source = SourceWorkRepository(session).require(result.source_work.id)
        stored_chunks = SourceChunkRepository(session).list_by_source_work(result.source_work.id)

    assert stored_source.title == "样本文本"
    assert stored_source.author == "作者"
    assert stored_source.source_type == "markdown"
    assert [chunk.text for chunk in stored_chunks] == ["第一段。", "第二段。"]

