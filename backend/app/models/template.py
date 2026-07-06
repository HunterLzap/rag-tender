"""填写模板数据模型：FillTemplate。

对应 SQLite 表 fill_templates。
"""

from typing import Optional

from pydantic import BaseModel


class FillTemplate(BaseModel):
    """填写模板模型，对应 fill_templates 表。

    Attributes:
        id: 主键，自增。
        tender_id: 外键，关联 tenders.id。
        filename: 模板文件名。
        file_path: 模板文件存储路径。
        file_type: 模板格式（docx/pdf/xlsx）。
        filled_path: 填写后的 DOCX 文件路径。
        output_pdf_path: 转换后的 PDF 文件路径。
        status: 填写状态（pending/filling/completed/failed）。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    tender_id: int = 0
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    filled_path: Optional[str] = None
    output_pdf_path: Optional[str] = None
    status: str = "pending"
    created_at: str = ""
