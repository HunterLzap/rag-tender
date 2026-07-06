"""投标待办清单请求 schema。"""

from typing import Optional

from pydantic import BaseModel


class SubmissionChecklistUpdate(BaseModel):
    """更新待办清单项的请求体。

    所有字段可选，仅更新传入的字段。

    Attributes:
        status: 状态（not_started / in_progress / done）。
        remark: 备注。
        item_name: 待办项名称。
        description: 详细说明。
    """

    status: Optional[str] = None
    remark: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None


class ManualItemCreate(BaseModel):
    """手动新增待办项的请求体。

    Attributes:
        item_name: 待办项名称（必填）。
        description: 详细说明。
        remark: 备注。
    """

    item_name: str
    description: Optional[str] = None
    remark: Optional[str] = None
