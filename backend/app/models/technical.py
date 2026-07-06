"""技术响应表数据模型。

对应 SQLite 表 technical_responses，用于 product_spec 类要求的
"标书要求值 vs 实际值"对比管理。
"""

from typing import Optional

from pydantic import BaseModel


class TechnicalResponse(BaseModel):
    """技术响应模型，对应 technical_responses 表。

    Attributes:
        id: 主键，自增。
        tender_id: 外键，关联 tenders.id。
        requirement_id: 外键，关联 tender_requirements.id。
        spec_name: 参数名称（从 requirement.title 派生）。
        required_value: 标书要求值（从 requirement content/numeric 派生）。
        actual_value: 实际值（用户手填）。
        is_hard: 是否硬性指标。
        remark: 备注。
        created_at: 记录创建时间（ISO 8601）。
        updated_at: 记录更新时间（ISO 8601）。
    """

    id: Optional[int] = None
    tender_id: int = 0
    requirement_id: int = 0
    spec_name: Optional[str] = None
    required_value: Optional[str] = None
    actual_value: Optional[str] = None
    response_status: str = "pending"
    is_hard: bool = True
    remark: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
