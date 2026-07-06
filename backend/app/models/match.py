"""匹配结果数据模型：MatchResult。

对应 SQLite 表 match_results。
"""

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.knowledge import Qualification
from app.models.tender import TenderRequirement


class MatchEvidenceItem(BaseModel):
    """字段级证据核验项。"""

    check_key: str
    label: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    status: str = "unknown"
    reason: Optional[str] = None
    critical: bool = True


class MatchResult(BaseModel):
    """匹配结果模型，对应 match_results 表。

    Attributes:
        id: 主键，自增。
        tender_id: 外键，关联 tenders.id。
        requirement_id: 外键，关联 tender_requirements.id。
        qualification_id: 外键，关联 qualifications.id（可为空，表示知识库中无匹配）。
        status: 匹配状态（matched/unmatched/needs_review）。
        reason: 匹配原因说明。
        mismatch_detail: 不符合的具体点（P0-07 要求①）。
        expected_qualification: 期望资质描述（P0-07 要求②）。
        in_knowledge_base: 知识库是否已有该资质（P0-07 要求③）。
        similarity_score: 语义相似度分数（0.0 ~ 1.0）。
        evidence_items: 字段级证据核验矩阵。
        confirmed_status: 人工确认状态（null/confirmed/rejected）。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    tender_id: int = 0
    requirement_id: int = 0
    qualification_id: Optional[int] = None
    status: str = "needs_review"
    reason: Optional[str] = None
    mismatch_detail: Optional[str] = None
    expected_qualification: Optional[str] = None
    in_knowledge_base: bool = False
    similarity_score: Optional[float] = None
    evidence_items: list[MatchEvidenceItem] = Field(default_factory=list)
    confirmed_status: Optional[str] = None
    created_at: str = ""
    requirement: Optional[TenderRequirement] = None
    qualification: Optional[Qualification] = None

    @field_validator("evidence_items", mode="before")
    @classmethod
    def _parse_evidence_items(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return value
