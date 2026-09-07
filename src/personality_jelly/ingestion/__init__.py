"""Source text loading and chunking."""

from personality_jelly.ingestion.chunker import ChunkingConfig, chunk_source_text
from personality_jelly.ingestion.loader import LoadedSource, load_text_source
from personality_jelly.ingestion.service import (
    SourceIngestionResult,
    ingest_loaded_source,
    ingest_text_file,
)

__all__ = [
    "ChunkingConfig",
    "LoadedSource",
    "SourceIngestionResult",
    "chunk_source_text",
    "ingest_loaded_source",
    "ingest_text_file",
    "load_text_source",
]

