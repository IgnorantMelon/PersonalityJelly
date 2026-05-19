"""Source text loading and chunking."""

from personality_jelly.ingestion.chunker import ChunkingConfig, chunk_source_text
from personality_jelly.ingestion.loader import LoadedSource, load_text_source

__all__ = ["ChunkingConfig", "LoadedSource", "chunk_source_text", "load_text_source"]

