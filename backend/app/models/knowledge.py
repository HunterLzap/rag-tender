"""知识库相关数据模型：KnowledgeFile 和 Qualification。

对应 SQLite 表 knowledge_files 和 qualifications。
"""

from typing import Optional

from pydantic import BaseModel


class KnowledgeFile(BaseModel):
    """知识库文件模型，对应 knowledge_files 表。

    Attributes:
        id: 主键，自增。
        filename: 上传时的文件名。
        file_path: 文件存储路径。
        file_type: 文件类型（pdf/docx/xlsx/image）。
        category: 分类（enterprise/personnel/performance/financial）。
        status: 解析状态（pending/parsing/completed/failed）。
        upload_time: 上传时间（ISO 8601）。
        parsed_at: 解析完成时间（ISO 8601）。
        extracted_text: 已提取/OCR 的文本缓存。
        extracted_at: 文本缓存生成时间（ISO 8601）。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    filename: str = ""
    file_path: str = ""
    file_type: Optional[str] = None
    category: Optional[str] = None
    status: str = "pending"
    upload_time: Optional[str] = None
    parsed_at: Optional[str] = None
    extracted_text: Optional[str] = None
    extracted_at: Optional[str] = None
    created_at: str = ""


class Qualification(BaseModel):
    """资质信息模型，对应 qualifications 表。

    Attributes:
        id: 主键，自增。
        file_id: 外键，关联 knowledge_files.id。
        name: 证书名称。
        number: 证书编号。
        issue_date: 发证日期。
        expiry_date: 有效期至。
        issuing_authority: 发证机构。
        scope: 认证范围。
        level: 等级。
        holder: 持证主体。
        category: 分类（enterprise/personnel/performance/financial）。
        status: 状态（valid/expiring/expired），由 expiry_date 计算。
        raw_text: 原始文本。
        created_at: 记录创建时间（ISO 8601）。
    """

    id: Optional[int] = None
    file_id: Optional[int] = None
    name: Optional[str] = None
    number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    scope: Optional[str] = None
    level: Optional[str] = None
    holder: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: str = ""
