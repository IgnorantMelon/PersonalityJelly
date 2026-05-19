from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain import ClaimStatus


class VerifierDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    claim_id: str
    status: ClaimStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class VerifierConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_a_id: str
    claim_b_id: str
    description: str
    resolution: str | None = None


class VerifierResult(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    decisions: list[VerifierDecision] = Field(default_factory=list)
    conflicts: list[VerifierConflict] = Field(default_factory=list)

