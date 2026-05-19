from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import SourceChunk, SourceWork
from personality_jelly.ingestion.chunker import ChunkingConfig, chunk_source_text
from personality_jelly.ingestion.loader import LoadedSource, load_text_source
from personality_jelly.storage import SourceChunkRepository, SourceWorkRepository


@dataclass(frozen=True)
class SourceIngestionResult:
    source_work: SourceWork
    chunks: list[SourceChunk]


def ingest_loaded_source(
    session: Session,
    loaded_source: LoadedSource,
    *,
    source_work_id: str | None = None,
    author: str | None = None,
    language: str = "zh-CN",
    chunking_config: ChunkingConfig | None = None,
) -> SourceIngestionResult:
    source_work = SourceWork(
        id=source_work_id or generate_id(EntityKind.SOURCE_WORK),
        title=loaded_source.title,
        author=author,
        language=language,
        source_type=loaded_source.source_type,
    )
    chunks = chunk_source_text(
        source_work_id=source_work.id,
        text=loaded_source.text,
        config=chunking_config,
    )

    SourceWorkRepository(session).add(source_work)
    SourceChunkRepository(session).add_many(chunks)

    return SourceIngestionResult(source_work=source_work, chunks=chunks)


def ingest_text_file(
    session: Session,
    path: str | Path,
    *,
    title: str | None = None,
    author: str | None = None,
    language: str = "zh-CN",
    encoding: str = "utf-8",
    chunking_config: ChunkingConfig | None = None,
) -> SourceIngestionResult:
    loaded_source = load_text_source(path=path, title=title, encoding=encoding)
    return ingest_loaded_source(
        session,
        loaded_source,
        author=author,
        language=language,
        chunking_config=chunking_config,
    )

