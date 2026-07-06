"""自动填写路由：上传模板/触发填写/下载结果。

所有端点前缀为 ``/fill``，由 main.py 挂载到 ``/api/v1`` 下。
"""

import logging
import os

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import FileResponse

from app.services import fill_service
from app.services.tender_service import get_tender
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fill", tags=["自动填写"])


@router.post("/{tender_id}/template", summary="上传投标模板")
async def upload_template(
    tender_id: int,
    file: UploadFile = File(...),
) -> dict:
    """上传投标文件模板（DOCX/PDF/XLSX）。

    Args:
        tender_id: 标书 ID。
        file: 上传的模板文件。

    Returns:
        统一响应，data 为模板信息。
    """
    tender = await get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    try:
        file_content = await file.read()
        template = await fill_service.upload_template(
            tender_id, file.filename or "template.docx", file_content
        )
        return success_response(
            data=template.model_dump(),
            message="模板上传成功",
        )
    except ValueError as e:
        logger.warning("模板上传校验失败: %s", str(e))
        return error_response(ErrorCode.FILE_FORMAT_UNSUPPORTED, str(e))
    except Exception as e:
        logger.error("模板上传失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"上传失败: {str(e)}")


@router.post("/{tender_id}", summary="触发自动填写")
async def fill_template(
    tender_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """触发自动填写（异步执行）。

    根据匹配结果将资质信息填入模板，生成 DOCX + PDF 双输出。
    通过 BackgroundTask 异步执行。

    Args:
        tender_id: 标书 ID。
        background_tasks: FastAPI 后台任务。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": "filling"}``。
    """
    tender = await get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    # 添加后台填写任务
    async def _fill_task() -> None:
        """后台填写任务包装。"""
        try:
            await fill_service.fill_template(tender_id)
        except Exception as e:
            logger.error("后台填写任务失败: tender_id=%s, error=%s", tender_id, str(e))

    background_tasks.add_task(_fill_task)

    return success_response(
        data={"tender_id": tender_id, "status": "filling"},
        message="填写任务已提交",
    )


@router.get("/{tender_id}/download", summary="下载填写结果", response_model=None)
async def download_filled(
    tender_id: int,
    format: str = "docx",
):
    """下载填写结果文件。

    Args:
        tender_id: 标书 ID。
        format: 下载格式（docx/pdf）。

    Returns:
        文件流响应或错误响应。
    """
    valid_formats = {"docx", "pdf"}
    if format not in valid_formats:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            f"format 必须是 {valid_formats} 之一",
        )

    try:
        result = await fill_service.download_filled(tender_id, format)
        if result is None:
            return error_response(
                ErrorCode.PARAM_VALIDATION_FAILED,
                f"标书 {tender_id} 暂无填写结果，请先完成自动填写",
            )

        file_path, filename = result
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if format == "docx"
            else "application/pdf"
        )

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )
    except Exception as e:
        logger.error("下载填写结果失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"下载失败: {str(e)}")
