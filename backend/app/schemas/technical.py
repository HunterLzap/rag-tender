"""技术响应表请求 schema。"""

from typing import List, Optional

from pydantic import BaseModel


class TechnicalResponseUpdate(BaseModel):
    """更新单条技术响应的请求体。

    所有字段可选，仅更新传入的字段。

    Attributes:
        actual_value: 实际值（用户手填）。
        remark: 备注。
        is_hard: 是否硬性指标。
    """

    actual_value: Optional[str] = None
    response_status: Optional[str] = None
    remark: Optional[str] = None
    is_hard: Optional[bool] = None


class TechnicalResponseBatchItem(BaseModel):
    """批量更新中的单条技术响应。

    Attributes:
        id: 技术响应记录 ID。
        actual_value: 实际值。
        remark: 备注。
    """

    id: int
    actual_value: Optional[str] = None
    response_status: Optional[str] = None
    remark: Optional[str] = None


class TechnicalResponseBatchUpdate(BaseModel):
    """批量更新技术响应的请求体。

    Attributes:
        items: 要更新的技术响应列表。
    """

    items: List[TechnicalResponseBatchItem]
