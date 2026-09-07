from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SOURCE_SUFFIXES = {
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
}


@dataclass(frozen=True)
class LoadedSource:
    title: str
    source_type: str
    text: str
    path: Path | None = None


def load_text_source(path: str | Path, title: str | None = None, encoding: str = "utf-8") -> LoadedSource:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_SOURCE_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_SUFFIXES))
        raise ValueError(f"Unsupported source file type {suffix!r}; expected one of: {supported}")

    text = source_path.read_text(encoding=encoding)
    return LoadedSource(
        title=title or source_path.stem,
        source_type=SUPPORTED_SOURCE_SUFFIXES[suffix],
        text=text,
        path=source_path,
    )

