"""匹配路由：触发匹配/查询结果/人工确认。

所有端点前缀为 ``/match``，由 main.py 挂载到 ``/api/v1`` 下。
"""

import logging

from fastapi import APIRouter, BackgroundTasks

from app.schemas.match import MatchConfirmRequest
from app.services import match_service
from app.services.tender_service import get_tender
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/match", tags=["匹配引擎"])


@router.post("/{tender_id}", summary="触发匹配")
async def match_tender(
    tender_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """触发标书匹配（异步执行）。

    通过 BackgroundTask 异步执行匹配流程，立即返回。
    前端轮询 GET /match/{tender_id} 获取结果。

    Args:
        tender_id: 标书 ID。
        background_tasks: FastAPI 后台任务。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": "matching"}``。
    """
    tender = await get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    # 先同步清除旧结果，避免前端轮询误读上一轮匹配数据。
    await match_service.clear_match_results(tender_id)
    match_service.start_match_progress(tender_id)

    # 添加后台匹配任务
    background_tasks.add_task(match_service.match_tender_background, tender_id)

    return success_response(
        data={"tender_id": tender_id, "status": "matching"},
        message="匹配任务已提交",
    )


@router.get("/{tender_id}/status", summary="获取匹配进度")
async def get_match_status(tender_id: int) -> dict:
    """获取标书匹配任务的实时进度。"""
    return success_response(data=match_service.get_match_progress(tender_id))


@router.get("/corrections", summary="获取人工纠错记录")
async def get_match_corrections(limit: int = 100) -> dict:
    """获取人工确认产生的错例记录。"""
    try:
        corrections = await match_service.list_match_corrections(limit=limit)
        return success_response(data=corrections)
    except Exception as e:
        logger.error("获取匹配纠错记录失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取失败: {str(e)}")


@router.get("/{tender_id}", summary="获取匹配结果")
async def get_match_results(tender_id: int) -> dict:
    """获取标书的匹配结果列表。

    包含每条标书要求的匹配状态、不符合详情、期望资质、知识库检查状态。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为匹配结果列表。
    """
    try:
        results = await match_service.get_match_results(tender_id)
        return success_response(data=[r.model_dump() for r in results])
    except Exception as e:
        logger.error("获取匹配结果失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取失败: {str(e)}")


@router.put("/{match_id}/confirm", summary="人工确认匹配结果")
async def confirm_match(match_id: int, req: MatchConfirmRequest) -> dict:
    """人工确认匹配结果（P1-02）。

    对"需人工确认"的匹配结果，用户可手动标注最终结论。

    Args:
        match_id: 匹配结果 ID。
        req: 确认请求体（confirmed_status: matched/unmatched/needs_review/confirmed）。

    Returns:
        统一响应，data 为更新后的匹配结果。
    """
    valid_statuses = {"matched", "unmatched", "needs_review", "confirmed"}
    if req.confirmed_status not in valid_statuses:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            f"confirmed_status 必须是 {valid_statuses} 之一",
        )
    if not req.correction_reason or not req.correction_reason.strip():
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            "人工确认必须填写修正原因",
        )

    try:
        result = await match_service.confirm_match(
            match_id,
            req.confirmed_status,
            req.correction_reason,
        )
        if result is None:
            return error_response(
                ErrorCode.PARAM_VALIDATION_FAILED, f"匹配结果 {match_id} 不存在"
            )
        return success_response(data=result.model_dump(), message="确认成功")
    except Exception as e:
        logger.error("确认匹配结果失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"确认失败: {str(e)}")
