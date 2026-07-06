"""投标待办清单路由。

端点前缀为 ``/tenders/{tender_id}/checklist``，由 main.py 挂载到 ``/api/v1`` 下。
首次 GET 时自动从 submission 类要求初始化待办清单。
支持手动新增不在标书中的待办项。
"""

import logging

from fastapi import APIRouter

from app.schemas.checklist import ManualItemCreate, SubmissionChecklistUpdate
from app.services import check_report_service
from app.services import submission_checklist_service as checklist_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenders", tags=["投标待办清单"])


@router.get("/{tender_id}/checklist", summary="获取待办清单")
async def get_checklist(tender_id: int) -> dict:
    """获取标书的待办清单（首次访问自动初始化）。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为 SubmissionChecklist 列表。
    """
    try:
        items = await checklist_service.get_all(tender_id)
        return success_response(data=[item.model_dump() for item in items])
    except Exception as e:
        logger.error("获取待办清单失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取待办清单失败: {str(e)}")


@router.post("/{tender_id}/checklist", summary="手动新增待办项")
async def add_manual_checklist_item(
    tender_id: int,
    req: ManualItemCreate,
) -> dict:
    """手动新增不在标书中的待办项。

    Args:
        tender_id: 标书 ID。
        req: 包含 item_name / description / remark 的请求体。

    Returns:
        统一响应，data 为新创建的 SubmissionChecklist。
    """
    try:
        result = await checklist_service.add_manual_item(tender_id, req)
        return success_response(data=result.model_dump(), message="待办项已新增")
    except Exception as e:
        logger.error("新增待办项失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"新增失败: {str(e)}")


@router.put("/{tender_id}/checklist/{item_id}", summary="更新待办状态")
async def update_checklist_item(
    tender_id: int,
    item_id: int,
    req: SubmissionChecklistUpdate,
) -> dict:
    """更新待办清单项的状态/备注/名称/描述。

    Args:
        tender_id: 标书 ID。
        item_id: 待办清单记录 ID。
        req: 更新请求体。

    Returns:
        统一响应，data 为更新后的 SubmissionChecklist。
    """
    try:
        result = await checklist_service.update(item_id, req)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "待办项不存在或状态值无效")
        return success_response(data=result.model_dump(), message="更新成功")
    except Exception as e:
        logger.error("更新待办项失败: item_id=%s, error=%s", item_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"更新失败: {str(e)}")


@router.get("/{tender_id}/check-report", summary="获取检查报告")
async def get_check_report(tender_id: int) -> dict:
    """获取结构化检查报告。"""
    try:
        result = await check_report_service.build_check_report(tender_id)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "标书不存在")
        return success_response(data=result)
    except Exception as e:
        logger.error("获取检查报告失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取检查报告失败: {str(e)}")


@router.get("/{tender_id}/check-report/export", summary="导出检查报告")
async def export_check_report(tender_id: int) -> dict:
    """导出 Markdown 检查报告。"""
    try:
        result = await check_report_service.export_check_report_markdown(tender_id)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "标书不存在")
        return success_response(data=result, message="检查报告已生成")
    except Exception as e:
        logger.error("导出检查报告失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"导出检查报告失败: {str(e)}")
