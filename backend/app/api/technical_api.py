"""技术响应表路由。

端点前缀为 ``/tenders/{tender_id}/technical``，由 main.py 挂载到 ``/api/v1`` 下。
首次 GET 时自动从 product_spec 类要求初始化技术响应记录。
"""

import logging

from fastapi import APIRouter

from app.schemas.technical import (
    TechnicalResponseBatchUpdate,
    TechnicalResponseUpdate,
)
from app.services import technical_response_service as tr_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenders", tags=["技术响应表"])


@router.get("/{tender_id}/technical", summary="获取技术响应表")
async def get_technical_responses(tender_id: int) -> dict:
    """获取标书的技术响应表（首次访问自动初始化）。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为 TechnicalResponse 列表。
    """
    try:
        responses = await tr_service.get_all(tender_id)
        return success_response(data=[r.model_dump() for r in responses])
    except Exception as e:
        logger.error("获取技术响应表失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取技术响应表失败: {str(e)}")


@router.put("/{tender_id}/technical/batch", summary="批量更新技术响应")
async def batch_update_technical_responses(
    tender_id: int,
    req: TechnicalResponseBatchUpdate,
) -> dict:
    """批量更新技术响应实际值。

    Args:
        tender_id: 标书 ID。
        req: 包含 items 列表的请求体。

    Returns:
        统一响应，data 为更新后的 TechnicalResponse 列表。
    """
    try:
        items = [item.model_dump() for item in req.items]
        updated = await tr_service.batch_update(tender_id, items)
        return success_response(
            data=[r.model_dump() for r in updated],
            message="批量更新成功",
        )
    except Exception as e:
        logger.error("批量更新技术响应失败: tender_id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"批量更新失败: {str(e)}")


@router.put("/{tender_id}/technical/{response_id}", summary="更新技术响应")
async def update_technical_response(
    tender_id: int,
    response_id: int,
    req: TechnicalResponseUpdate,
) -> dict:
    """更新单条技术响应（实际值/备注/是否硬性）。

    Args:
        tender_id: 标书 ID。
        response_id: 技术响应记录 ID。
        req: 更新请求体。

    Returns:
        统一响应，data 为更新后的 TechnicalResponse。
    """
    try:
        result = await tr_service.update(response_id, req)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "技术响应记录不存在")
        return success_response(data=result.model_dump(), message="更新成功")
    except Exception as e:
        logger.error("更新技术响应失败: response_id=%s, error=%s", response_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"更新失败: {str(e)}")
