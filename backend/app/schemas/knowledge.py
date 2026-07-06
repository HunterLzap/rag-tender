"""知识库相关 Pydantic schema。"""

from typing import Optional

from pydantic import BaseModel

from app.models.knowledge import KnowledgeFile, Qualification


class KnowledgeFileResponse(BaseModel):
    """知识库文件响应。

    Attributes:
        file_id: 文件 ID。
        status: 解析状态。
    """

    file_id: int
    status: str


class QualificationCreate(BaseModel):
    """手动新增资质请求体。

    Attributes:
        file_id: 关联的知识库文件 ID（可为空，表示手动新增）。
        name: 证书名称。
        number: 证书编号。
        issue_date: 发证日期。
        expiry_date: 有效期至。
        issuing_authority: 发证机构。
        scope: 认证范围。
        level: 等级。
        holder: 持证主体。
        category: 分类。
        status: 状态。
        raw_text: 原始文本。
    """

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


class QualificationUpdate(BaseModel):
    """资质编辑请求体（所有字段可选）。

    Attributes:
        name: 证书名称。
        number: 证书编号。
        issue_date: 发证日期。
        expiry_date: 有效期至。
        issuing_authority: 发证机构。
        scope: 认证范围。
        level: 等级。
        holder: 持证主体。
        category: 分类。
        status: 状态。
    """

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


class QualificationBulkCategoryUpdate(BaseModel):
    """批量修改资质分类请求体。"""

    qualification_ids: list[int]
    category: str


class QualificationBulkDelete(BaseModel):
    """批量删除资质请求体。"""

    qualification_ids: list[int]


class QualificationResponse(Qualification):
    """资质响应（继承 Qualification 模型）。"""

    pass
