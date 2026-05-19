from pathlib import Path

import pytest

from personality_jelly.ingestion import ChunkingConfig, chunk_source_text, load_text_source


def test_load_text_source_detects_markdown(tmp_path: Path) -> None:
    source_file = tmp_path / "novel.md"
    source_file.write_text("# 第一章\n\n内容", encoding="utf-8")

    loaded = load_text_source(source_file)

    assert loaded.title == "novel"
    assert loaded.source_type == "markdown"
    assert loaded.text.startswith("# 第一章")


def test_load_text_source_rejects_unknown_suffix(tmp_path: Path) -> None:
    source_file = tmp_path / "novel.epub"
    source_file.write_text("内容", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported source file type"):
        load_text_source(source_file)


def test_chunk_source_text_tracks_chapters_and_stable_ids() -> None:
    text = (
        "# 第一章 雨夜\n\n"
        "她站在窗前，听见远处的钟声。\n\n"
        "第2章 归来\n\n"
        "他回到城中，带着旧日的秘密。"
    )

    first = chunk_source_text("sw_001", text)
    second = chunk_source_text("sw_001", text)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert [chunk.chapter_index for chunk in first] == [1, 2]
    assert first[0].chapter_title == "第一章 雨夜"
    assert second[1].chapter_title == "归来"
    assert first[0].paragraph_index == 0
    assert first[1].paragraph_index == 0


def test_chunk_source_text_splits_long_paragraph() -> None:
    text = "第一章\n\n第一句很长。" * 10

    chunks = chunk_source_text(
        "sw_001",
        text,
        config=ChunkingConfig(max_paragraph_chars=12),
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 12 for chunk in chunks)

