from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from personality_jelly.domain import Character, SourceChunk
from personality_jelly.storage import SourceChunkRepository


MAX_QUERY_TERMS = 12


@dataclass(frozen=True)
class KeywordRetrievalResult:
    chunks: list[SourceChunk]
    query_terms: list[str]


def retrieve_source_chunks(
    session: Session,
    *,
    source_work_id: str,
    character: Character,
    query: str,
    limit: int = 4,
) -> KeywordRetrievalResult:
    if limit < 1:
        raise ValueError("limit must be greater than 0")

    chunks = SourceChunkRepository(session).list_by_source_work(source_work_id)
    query_terms = _query_terms(query=query, character=character)
    if not query_terms:
        return KeywordRetrievalResult(chunks=[], query_terms=[])

    scored = [
        (_score_chunk(chunk, query_terms), index, chunk)
        for index, chunk in enumerate(chunks)
    ]
    matched = [
        (score, index, chunk)
        for score, index, chunk in scored
        if score > 0
    ]
    matched.sort(key=lambda item: (-item[0], item[1]))
    return KeywordRetrievalResult(
        chunks=[chunk for _, _, chunk in matched[:limit]],
        query_terms=query_terms,
    )


def _query_terms(*, query: str, character: Character) -> list[str]:
    seeds = [character.canonical_name, *character.aliases]
    seeds.extend(_tokenize(query))

    terms: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        normalized = seed.strip().lower()
        if len(normalized) < 2:
            continue
        if normalized in seen:
            continue
        terms.append(normalized)
        seen.add(normalized)
        if len(terms) >= MAX_QUERY_TERMS:
            break
    return terms


def _tokenize(text: str) -> list[str]:
    ascii_tokens = re.findall(r"[a-zA-Z0-9_]{2,}", text)
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    terms: list[str] = []
    for token in [*ascii_tokens, *cjk_tokens]:
        terms.extend(_split_cjk_token(token) if _is_cjk_token(token) else [token])
    return terms


def _split_cjk_token(token: str) -> list[str]:
    if len(token) <= 4:
        return [token]
    return [
        token[index : index + 2]
        for index in range(0, len(token) - 1)
    ]


def _is_cjk_token(token: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff]+", token))


def _score_chunk(chunk: SourceChunk, terms: list[str]) -> int:
    text = chunk.text.lower()
    score = 0
    for index, term in enumerate(terms):
        occurrences = text.count(term)
        if not occurrences:
            continue
        weight = 3 if index == 0 else 1
        score += occurrences * weight
    return score
