from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from personality_jelly.domain import SourceChunk


_CHAPTER_PATTERNS = (
    re.compile(r"^\s*#{1,3}\s+(?P<title>.+?)\s*$"),
    re.compile(r"^\s*第[零〇一二三四五六七八九十百千万\d]+[章节回卷部集]\s*(?P<title>.*?)\s*$"),
)


@dataclass(frozen=True)
class ChunkingConfig:
    max_paragraph_chars: int = 1200
    min_paragraph_chars: int = 1


@dataclass(frozen=True)
class _Paragraph:
    text: str
    char_start: int
    char_end: int
    chapter_index: int | None
    chapter_title: str | None
    paragraph_index: int


def chunk_source_text(
    source_work_id: str,
    text: str,
    config: ChunkingConfig | None = None,
) -> list[SourceChunk]:
    active_config = config or ChunkingConfig()
    paragraphs = list(_iter_paragraphs(text, active_config))

    return [
        SourceChunk(
            id=_stable_chunk_id(source_work_id, paragraph),
            source_work_id=source_work_id,
            chapter_index=paragraph.chapter_index,
            chapter_title=paragraph.chapter_title,
            paragraph_index=paragraph.paragraph_index,
            text=paragraph.text,
            char_start=paragraph.char_start,
            char_end=paragraph.char_end,
        )
        for paragraph in paragraphs
    ]


def _iter_paragraphs(text: str, config: ChunkingConfig) -> list[_Paragraph]:
    chapter_index: int | None = None
    chapter_title: str | None = None
    paragraph_index = 0
    paragraphs: list[_Paragraph] = []

    for match in re.finditer(r"\S(?:.*?)(?=\r?\n\s*\r?\n|\Z)", text, flags=re.DOTALL):
        raw_paragraph = match.group(0)
        normalized = _normalize_paragraph(raw_paragraph)
        if len(normalized) < config.min_paragraph_chars:
            continue

        detected_title = _detect_chapter_title(normalized)
        if detected_title is not None:
            chapter_index = 1 if chapter_index is None else chapter_index + 1
            chapter_title = detected_title
            paragraph_index = 0
            continue

        for chunk_text, offset in _split_long_paragraph(normalized, config.max_paragraph_chars):
            paragraphs.append(
                _Paragraph(
                    text=chunk_text,
                    char_start=match.start() + offset,
                    char_end=match.start() + offset + len(chunk_text),
                    chapter_index=chapter_index,
                    chapter_title=chapter_title,
                    paragraph_index=paragraph_index,
                )
            )
            paragraph_index += 1

    return paragraphs


def _detect_chapter_title(paragraph: str) -> str | None:
    single_line = "\n" not in paragraph
    if not single_line:
        return None

    for pattern in _CHAPTER_PATTERNS:
        match = pattern.match(paragraph)
        if not match:
            continue
        title = match.group("title").strip()
        return title or paragraph.strip()
    return None


def _normalize_paragraph(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[tuple[str, int]]:
    if len(paragraph) <= max_chars:
        return [(paragraph, 0)]

    parts: list[tuple[str, int]] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        if end < len(paragraph):
            split_at = max(
                paragraph.rfind("。", start, end),
                paragraph.rfind("！", start, end),
                paragraph.rfind("？", start, end),
                paragraph.rfind(".", start, end),
                paragraph.rfind("!", start, end),
                paragraph.rfind("?", start, end),
            )
            if split_at > start:
                end = split_at + 1

        part = paragraph[start:end].strip()
        if part:
            leading_trim = len(paragraph[start:end]) - len(paragraph[start:end].lstrip())
            parts.append((part, start + leading_trim))
        start = end

    return parts


def _stable_chunk_id(source_work_id: str, paragraph: _Paragraph) -> str:
    raw = "|".join(
        [
            source_work_id,
            str(paragraph.chapter_index),
            str(paragraph.paragraph_index),
            str(paragraph.char_start),
            str(paragraph.char_end),
            paragraph.text,
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"chunk_{digest}"

