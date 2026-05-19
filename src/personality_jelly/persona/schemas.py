from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersonaCompilation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_self: str
    speech_rules: list[str] = Field(default_factory=list)
    behavior_rules: list[str] = Field(default_factory=list)
    world_adaptation_rules: list[str] = Field(default_factory=list)
    forbidden_rules: list[str] = Field(default_factory=list)

