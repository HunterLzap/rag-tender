"""投标待办清单数据模型。

对应 SQLite 表 submission_checklist，用于 submission 类要求的
三档状态（未开始/进行中/已完成）管理。
"""

from typing import Optional

from pydantic import BaseModel


class SubmissionChecklist(BaseModel):
    """待办清单模型，对应 submission_checklist 表。

    Attributes:
        id: 主键，自增。
        tender_id: 外键，关联 tenders.id。
        requirement_id: 外键，关联 tender_requirements.id（手动新增的项可为 None）。
        item_name: 待办项名称。
        description: 详细说明。
        status: 状态（not_started / in_progress / done）。
        remark: 备注（灰色地带提示等）。
        created_at: 记录创建时间（ISO 8601）。
        updated_at: 记录更新时间（ISO 8601）。
    """

    id: Optional[int] = None
    tender_id: int = 0
    requirement_id: Optional[int] = None
    item_name: str = ""
    description: Optional[str] = None
    status: str = "not_started"
    remark: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
