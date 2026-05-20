from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummaryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
