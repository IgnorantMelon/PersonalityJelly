from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain import MemoryScope, MemoryStatus


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    scope: MemoryScope
    status: MemoryStatus
    content: str
    importance: float = Field(ge=0.0, le=1.0)
    reason: str


class MemoryCuration(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    memories: list[MemoryCandidate] = Field(default_factory=list)

