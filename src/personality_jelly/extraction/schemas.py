from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain import ClaimType


class ReaderEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    chunk_id: str
    excerpt: str
    support_score: float = Field(ge=0.0, le=1.0)


class ReaderClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    claim_type: ClaimType
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    evidence: list[ReaderEvidenceRef] = Field(default_factory=list)


class ReaderExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    claims: list[ReaderClaim] = Field(default_factory=list)

