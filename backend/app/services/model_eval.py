from typing import Literal

from pydantic import BaseModel, Field


class SemanticAssessment(BaseModel):
    verdict: Literal["supports", "contradicts", "insufficient"] = "insufficient"
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
