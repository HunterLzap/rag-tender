"""标书相关 Pydantic schema。"""

from typing import List, Optional

from pydantic import BaseModel

from app.models.tender import Tender, TenderRequirement


class TenderUploadResponse(BaseModel):
    """标书上传响应。

    Attributes:
        tender_id: 标书 ID。
        status: 当前状态。
    """

    tender_id: int
    status: str


class TenderRequirementUpdate(BaseModel):
    """标书要求编辑请求体。

    所有字段可选，仅更新传入的字段（P1-01 人工校对）。

    Attributes:
        category: 要求分类。
        title: 要求标题。
        content: 要求描述。
        is_hard: 是否硬性要求。
        raw_text: 原始文本。
        page_number: 页码。
        numeric_value: 数值规则值。
        numeric_operator: 数值运算符。
        numeric_unit: 数值单位。
    """

    category: Optional[str] = None
    requirement_nature: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    is_hard: Optional[bool] = None
    raw_text: Optional[str] = None
    page_number: Optional[int] = None
    numeric_value: Optional[str] = None
    numeric_operator: Optional[str] = None
    numeric_unit: Optional[str] = None
    review_status: Optional[str] = None


class TenderRequirementBatchStatus(BaseModel):
    """批量更新解析确认状态。"""

    requirement_ids: List[int]
    review_status: str


class TenderRequirementBatchDelete(BaseModel):
    """批量删除标书要求。"""

    requirement_ids: List[int]


class TenderDetail(BaseModel):
    """标书详情（含要求列表）。

    Attributes:
        tender: 标书基本信息。
        requirements: 标书要求列表。
    """

    tender: Tender
    requirements: List[TenderRequirement] = []
