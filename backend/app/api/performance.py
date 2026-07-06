"""业绩项目库 API。"""

import logging

from fastapi import APIRouter

from app.schemas.performance import PerformanceProjectCreate, PerformanceProjectUpdate
from app.services import performance_project_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["业绩项目库"])


@router.get("/projects", summary="业绩项目列表")
async def list_projects() -> dict:
    try:
        projects = await performance_project_service.list_projects()
        return success_response(data=[project.model_dump() for project in projects])
    except Exception as e:
        logger.error("获取业绩项目列表失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取业绩项目失败: {str(e)}")


@router.post("/projects", summary="新增业绩项目")
async def create_project(payload: PerformanceProjectCreate) -> dict:
    if not payload.project_name.strip():
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "项目名称不能为空")
    try:
        project = await performance_project_service.create_project(payload.model_dump())
        return success_response(data=project.model_dump(), message="业绩项目新增成功")
    except Exception as e:
        logger.error("新增业绩项目失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"新增业绩项目失败: {str(e)}")


@router.put("/projects/{project_id}", summary="编辑业绩项目")
async def update_project(project_id: int, payload: PerformanceProjectUpdate) -> dict:
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "project_name" in update_data and not update_data["project_name"].strip():
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "项目名称不能为空")
    try:
        project = await performance_project_service.update_project(project_id, update_data)
        if project is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"业绩项目 {project_id} 不存在")
        return success_response(data=project.model_dump(), message="业绩项目更新成功")
    except Exception as e:
        logger.error("编辑业绩项目失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"编辑业绩项目失败: {str(e)}")


@router.delete("/projects/{project_id}", summary="删除业绩项目")
async def delete_project(project_id: int) -> dict:
    try:
        deleted = await performance_project_service.delete_project(project_id)
        if not deleted:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"业绩项目 {project_id} 不存在")
        return success_response(data={"deleted": True}, message="业绩项目删除成功")
    except Exception as e:
        logger.error("删除业绩项目失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"删除业绩项目失败: {str(e)}")
