"""业绩项目库 API schema。"""

from typing import Optional

from pydantic import BaseModel


class PerformanceProjectCreate(BaseModel):
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


class PerformanceProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    contract_no: Optional[str] = None
    contract_amount: Optional[str] = None
    sign_date: Optional[str] = None
    completion_date: Optional[str] = None
    project_scope: Optional[str] = None
    year: Optional[str] = None
    file_ids: Optional[list[int]] = None
    remark: Optional[str] = None
