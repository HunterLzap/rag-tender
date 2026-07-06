"""标书相关数据模型：Tender 和 TenderRequirement。

对应 SQLite 表 tenders 和 tender_requirements。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Tender(BaseModel):
    """标书模型，对应 tenders 表。

    Attributes:
        id: 主键，自增。
        filename: 上传时的文件名。
        original_path: 原始文件存储路径。
        pdf_path: 转换后的 PDF 路径（非 PDF 文件转换后填充）。
        title: 标书标题（解析后提取）。
        file_type: 文件类型（pdf/docx/doc）。
        status: 解析状态（pending/converting/parsing/extracting/completed/failed）。
        total_pages: PDF 总页数。
        upload_time: 上传时间（ISO 8601）。
        parsed_at: 解析完成时间（ISO 8601）。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    filename: str = ""
    original_path: str = ""
    pdf_path: Optional[str] = None
    title: Optional[str] = None
    file_type: Optional[str] = None
    status: str = "pending"
    total_pages: int = 0
    region: Optional[str] = None
    procurement_type: Optional[str] = None
    budget: Optional[str] = None
    agency: Optional[str] = None
    upload_time: Optional[str] = None
    parsed_at: Optional[str] = None
    created_at: str = ""


class TenderRequirement(BaseModel):
    """标书要求模型，对应 tender_requirements 表。

    Attributes:
        id: 主键，自增。
        tender_id: 外键，关联 tenders.id。
        category: 要求分类（qualification/performance/financial/personnel/other/
                   product_spec/submission）。
        requirement_nature: 处理性质子维度（capability 走匹配 / submission 走待办清单）。
        title: 要求标题。
        content: 要求描述。
        is_hard: 是否为硬性要求。
        raw_text: 原始文本。
        page_number: 原文所在页码。
        numeric_value: 数值规则的值（如 "1000"）。
        numeric_operator: 数值规则的运算符（如 ">="）。
        numeric_unit: 数值规则的单位（如 "万元"）。
        review_status: 核对状态（pending/confirmed）。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    tender_id: int = 0
    category: str = "other"
    requirement_nature: str = "capability"
    title: Optional[str] = None
    content: Optional[str] = None
    is_hard: bool = True
    raw_text: Optional[str] = None
    page_number: Optional[int] = None
    numeric_value: Optional[str] = None
    numeric_operator: Optional[str] = None
    numeric_unit: Optional[str] = None
    review_status: str = "pending"
    created_at: str = ""
