from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import Character
from personality_jelly.storage import CharacterRepository, SourceWorkRepository


@dataclass(frozen=True)
class CharacterCreationResult:
    character: Character


def create_character(
    session: Session,
    *,
    source_work_id: str,
    canonical_name: str,
    aliases: list[str] | None = None,
    character_id: str | None = None,
) -> CharacterCreationResult:
    normalized_name = _normalize_name(canonical_name)
    if not normalized_name:
        raise ValueError("canonical_name must not be empty")

    SourceWorkRepository(session).require(source_work_id)

    repository = CharacterRepository(session)
    existing_names = {
        character.canonical_name for character in repository.list_by_source_work(source_work_id)
    }
    if normalized_name in existing_names:
        raise ValueError(
            f"Character {normalized_name!r} already exists for source work {source_work_id!r}"
        )

    character = Character(
        id=character_id or generate_id(EntityKind.CHARACTER),
        source_work_id=source_work_id,
        canonical_name=normalized_name,
        aliases=_normalize_aliases(aliases or [], canonical_name=normalized_name),
    )
    repository.add(character)
    return CharacterCreationResult(character=character)


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def _normalize_aliases(aliases: list[str], *, canonical_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        candidate = _normalize_name(alias)
        if not candidate or candidate == canonical_name or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized

