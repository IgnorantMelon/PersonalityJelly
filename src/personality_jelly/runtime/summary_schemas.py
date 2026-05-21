from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummaryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    short_term_scene_state: str = Field(
        min_length=1,
        description="Temporary scene, task, and unresolved context for continuing this conversation.",
    )
    user_memory_candidates: list[str] = Field(
        default_factory=list,
        description="Durable user preferences or facts that may be reviewed by the memory workflow.",
    )
    relationship_memory_notes: list[str] = Field(
        default_factory=list,
        description="Durable relationship changes between user and character.",
    )
    reflective_notes: list[str] = Field(
        default_factory=list,
        description="Non-canon operational lessons about interaction boundaries or failure risks.",
    )
