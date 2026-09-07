from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.domain import CriticAction, CriticRiskLevel


class CriticEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    ooc_risk: CriticRiskLevel
    fact_risk: CriticRiskLevel
    memory_risk: CriticRiskLevel
    mode_risk: CriticRiskLevel
    reasons: list[str] = Field(default_factory=list)
    suggested_action: CriticAction

