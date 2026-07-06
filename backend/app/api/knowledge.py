"""知识库路由：文件上传/解析/资质管理。

所有端点前缀为 ``/knowledge``，由 main.py 挂载到 ``/api/v1`` 下。
"""

import mimetypes
import os
import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.schemas.knowledge import (
    KnowledgeFileResponse,
    QualificationBulkCategoryUpdate,
    QualificationBulkDelete,
    QualificationCreate,
    QualificationUpdate,
)
from app.services import knowledge_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


_INLINE_PREVIEW_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
}


@router.post("/upload", summary="上传知识库文件")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form("enterprise"),
) -> dict:
    """上传知识库文件（自动触发解析）。

    支持 PDF/图片/DOCX/扫描件/XLSX，上传时选择分类。
    解析通过 BackgroundTask 异步执行。

    Args:
        background_tasks: FastAPI 后台任务。
        file: 上传的文件。
        category: 文件分类（enterprise/personnel/performance/financial）。

    Returns:
        统一响应，data 为 ``{"file_id": int, "status": "pending"}``。
    """
    valid_categories = {"enterprise", "personnel", "performance", "financial"}
    if category not in valid_categories:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            f"category 必须是 {valid_categories} 之一",
        )

    try:
        file_content = await file.read()
        kf = await knowledge_service.upload_file(
            file.filename or "unknown", file_content, category
        )

        # 添加后台解析任务
        background_tasks.add_task(knowledge_service.parse_file, kf.id)

        return success_response(
            data=KnowledgeFileResponse(file_id=kf.id or 0, status=kf.status).model_dump(),
            message="文件上传成功，解析已启动",
        )
    except ValueError as e:
        logger.warning("知识库文件上传校验失败: %s", str(e))
        return error_response(ErrorCode.FILE_FORMAT_UNSUPPORTED, str(e))
    except Exception as e:
        logger.error("知识库文件上传失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"上传失败: {str(e)}")


@router.get("/files", summary="文件列表")
async def list_files(category: str | None = None) -> dict:
    """获取知识库文件列表。

    Args:
        category: 分类筛选（可选）。

    Returns:
        统一响应，data 为文件列表。
    """
    try:
        files = await knowledge_service.list_files(category)
        return success_response(data=[f.model_dump() for f in files])
    except Exception as e:
        logger.error("获取文件列表失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取列表失败: {str(e)}")


@router.get("/files/{file_id}/status", summary="文件解析状态")
async def get_file_status(file_id: int) -> dict:
    """获取知识库文件解析状态。

    Args:
        file_id: 文件 ID。

    Returns:
        统一响应，data 为 ``{"file_id": int, "status": str}``。
    """
    status = await knowledge_service.get_file_status(file_id)
    if status is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"文件 {file_id} 不存在")
    return success_response(data=status)


@router.get("/files/{file_id}/preview", summary="预览或下载知识库文件", response_model=None)
async def preview_file(
    file_id: int,
    disposition: str = Query("inline", pattern="^(inline|attachment)$"),
):
    """返回知识库原文件，用于网页内预览或下载。"""
    try:
        kf = await knowledge_service.get_file(file_id)
        if kf is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"文件 {file_id} 不存在")
        if not kf.file_path or not os.path.isfile(kf.file_path):
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"文件 {file_id} 原文件不存在")

        media_type = mimetypes.guess_type(kf.filename)[0] or "application/octet-stream"
        content_disposition = disposition
        if disposition == "inline" and media_type not in _INLINE_PREVIEW_TYPES:
            content_disposition = "attachment"

        return FileResponse(
            path=kf.file_path,
            media_type=media_type,
            filename=kf.filename,
            content_disposition_type=content_disposition,
        )
    except Exception as e:
        logger.error("知识库文件预览失败: file_id=%s, error=%s", file_id, str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"预览失败: {str(e)}")


@router.delete("/files/{file_id}", summary="删除文件")
async def delete_file(file_id: int) -> dict:
    """删除知识库文件及其关联的资质记录和物理文件。

    Args:
        file_id: 知识库文件 ID。

    Returns:
        统一响应，删除成功返回 message。
    """
    try:
        deleted = await knowledge_service.delete_file(file_id)
        if not deleted:
            return error_response(
                ErrorCode.PARAM_VALIDATION_FAILED, f"文件 {file_id} 不存在"
            )
        return success_response(data={"deleted": True}, message="删除成功")
    except Exception as e:
        logger.error("删除知识库文件失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"删除失败: {str(e)}")


@router.post("/files/{file_id}/reparse", summary="重新解析文件")
async def reparse_file(file_id: int, background_tasks: BackgroundTasks) -> dict:
    """重新触发知识库文件解析。

    校验文件存在性及当前状态（非 pending/parsing），重置为 pending 后
    通过 BackgroundTask 启动异步解析。

    Args:
        file_id: 知识库文件 ID。
        background_tasks: FastAPI 后台任务。

    Returns:
        统一响应，返回 message。
    """
    try:
        await knowledge_service.prepare_reparse(file_id)
        background_tasks.add_task(knowledge_service.parse_file, file_id)
        return success_response(message="重新解析已启动")
    except ValueError as e:
        logger.warning("重新解析校验失败: file_id=%s, error=%s", file_id, str(e))
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, str(e))
    except Exception as e:
        logger.error("重新解析失败: file_id=%s, error=%s", file_id, str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"重新解析失败: {str(e)}")


@router.post("/qualifications/reparse-incomplete", summary="一键分析待补全资质")
async def reparse_incomplete_qualifications(
    background_tasks: BackgroundTasks,
    category: str | None = None,
) -> dict:
    """重新分析待补全资质对应的源文件。"""
    valid_categories = {"enterprise", "personnel", "financial", "other", None}
    if category not in valid_categories:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            f"category 必须是 {valid_categories} 之一",
        )
    try:
        file_ids = await knowledge_service.get_incomplete_qualification_file_ids(category)
        for file_id in file_ids:
            await knowledge_service.prepare_reparse(file_id)
            background_tasks.add_task(knowledge_service.parse_file, file_id)
        return success_response(
            data={"file_ids": file_ids, "submitted_count": len(file_ids)},
            message="待补全资质重新分析已启动",
        )
    except Exception as e:
        logger.error("一键分析待补全资质失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"一键分析失败: {str(e)}")


@router.get("/qualifications", summary="资质列表")
async def get_qualifications(category: str | None = None) -> dict:
    """获取资质列表（可按分类筛选）。

    Args:
        category: 分类筛选（可选）。

    Returns:
        统一响应，data 为资质列表。
    """
    try:
        quals = await knowledge_service.get_qualifications(category)
        return success_response(data=[q.model_dump() for q in quals])
    except Exception as e:
        logger.error("获取资质列表失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取列表失败: {str(e)}")


@router.post("/qualifications", summary="手动新增资质")
async def create_qualification(qual: QualificationCreate) -> dict:
    """手动新增资质记录（P0-06）。

    Args:
        qual: 资质创建请求体。

    Returns:
        统一响应，data 为创建的资质信息。
    """
    try:
        result = await knowledge_service.create_qualification(qual.model_dump())
        return success_response(data=result.model_dump() if result else None, message="资质新增成功")
    except Exception as e:
        logger.error("新增资质失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"新增失败: {str(e)}")


@router.post("/qualifications/bulk-category", summary="批量修改资质分类")
async def bulk_update_qualification_category(payload: QualificationBulkCategoryUpdate) -> dict:
    """批量修改资质分类，并同步修改关联源文件分类。"""
    valid_categories = {"enterprise", "personnel", "performance", "financial", "other"}
    if payload.category not in valid_categories:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            f"category 必须是 {valid_categories} 之一",
        )
    if not payload.qualification_ids:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "qualification_ids 不能为空")

    try:
        result = await knowledge_service.bulk_update_qualification_category(
            payload.qualification_ids,
            payload.category,
        )
        return success_response(data=result, message="批量修改分类成功")
    except Exception as e:
        logger.error("批量修改资质分类失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"批量修改失败: {str(e)}")


@router.post("/qualifications/bulk-delete-source", summary="按源文件批量删除资质")
async def bulk_delete_qualifications_by_source(payload: QualificationBulkDelete) -> dict:
    """按源文件语义批量删除资质和关联上传文件。"""
    if not payload.qualification_ids:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "qualification_ids 不能为空")

    try:
        result = await knowledge_service.bulk_delete_qualifications_by_source(
            payload.qualification_ids,
        )
        return success_response(data=result, message="批量删除成功")
    except Exception as e:
        logger.error("批量删除资质失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"批量删除失败: {str(e)}")


@router.put("/qualifications/{qual_id}", summary="编辑资质")
async def update_qualification(qual_id: int, qual: QualificationUpdate) -> dict:
    """编辑资质信息（P0-06）。

    Args:
        qual_id: 资质 ID。
        qual: 资质更新请求体（所有字段可选）。

    Returns:
        统一响应，data 为更新后的资质信息。
    """
    try:
        # 过滤掉 None 值，只更新传入的字段
        update_data = {k: v for k, v in qual.model_dump().items() if v is not None}
        result = await knowledge_service.update_qualification(qual_id, update_data)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"资质 {qual_id} 不存在")
        return success_response(data=result.model_dump(), message="资质更新成功")
    except Exception as e:
        logger.error("更新资质失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"更新失败: {str(e)}")


@router.delete("/qualifications/{qual_id}", summary="删除资质")
async def delete_qualification(qual_id: int) -> dict:
    """删除资质记录（P0-06）。

    Args:
        qual_id: 资质 ID。

    Returns:
        统一响应，删除成功返回 message。
    """
    try:
        deleted = await knowledge_service.delete_qualification(qual_id)
        if not deleted:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"资质 {qual_id} 不存在")
        return success_response(message="资质删除成功")
    except Exception as e:
        logger.error("删除资质失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"删除失败: {str(e)}")
