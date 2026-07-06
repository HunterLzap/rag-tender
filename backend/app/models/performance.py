"""业绩项目库模型。"""

from typing import Optional

from pydantic import BaseModel


class PerformanceProject(BaseModel):
    """业绩项目记录。"""

    id: Optional[int] = None
    project_name: str
    client_name: Optional[str] = None
    contract_no: Optional[str] = None
    contract_amount: Optional[str] = None
    sign_date: Optional[str] = None
    completion_date: Optional[str] = None
    project_scope: Optional[str] = None
    year: Optional[str] = None
    file_ids: list[int] = []
    remark: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
