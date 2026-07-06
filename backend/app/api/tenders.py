"""标书路由：上传/解析/查询/状态。

所有端点前缀为 ``/tenders``，由 main.py 挂载到 ``/api/v1`` 下。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import FileResponse

from app.schemas.tender import (
    TenderRequirementBatchDelete,
    TenderRequirementBatchStatus,
    TenderRequirementUpdate,
    TenderUploadResponse,
)
from app.services import tender_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenders", tags=["标书解析"])


@router.post("/upload", summary="上传标书文件")
async def upload_tender(file: UploadFile = File(...)) -> dict:
    """上传标书文件（PDF/DOCX/DOC）。

    保存文件并创建 Tender 记录（status=pending），返回 tender_id。
    解析需另行调用 POST /tenders/{tender_id}/parse 触发。

    Args:
        file: 上传的文件（multipart/form-data，字段名 file）。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": "pending"}``。
    """
    try:
        file_content = await file.read()
        tender = await tender_service.upload_tender(file.filename or "unknown.pdf", file_content)
        return success_response(
            data=TenderUploadResponse(tender_id=tender.id or 0, status=tender.status).model_dump(),
            message="标书上传成功",
        )
    except ValueError as e:
        logger.warning("标书上传校验失败: %s", str(e))
        return error_response(ErrorCode.FILE_FORMAT_UNSUPPORTED, str(e))
    except Exception as e:
        logger.error("标书上传失败: %s", str(e), exc_info=True)
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"上传失败: {str(e)}")


@router.post("/{tender_id}/parse", summary="触发标书解析")
async def parse_tender(
    tender_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """触发标书异步解析。

    通过 BackgroundTask 异步执行解析流程，立即返回。
    前端轮询 GET /tenders/{tender_id}/status 获取进度。

    Args:
        tender_id: 标书 ID。
        background_tasks: FastAPI 后台任务。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": "parsing"}``。
    """
    tender = await tender_service.get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    # 添加后台任务
    background_tasks.add_task(tender_service.parse_tender, tender_id)

    return success_response(
        data={"tender_id": tender_id, "status": "parsing"},
        message="解析任务已提交",
    )


@router.post("/{tender_id}/reparse", summary="按新分类重新解析")
async def reparse_tender(
    tender_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """按新分类体系重新解析标书要求。

    清空该标书下的所有旧数据（要求、匹配结果、技术响应、待办清单），
    然后后台重新调用解析流程（使用新的 7 类分类 + nature 字段）。

    Args:
        tender_id: 标书 ID。
        background_tasks: FastAPI 后台任务。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": "parsing"}``。
    """
    tender = await tender_service.get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    # 清空旧数据
    await tender_service.reparse_requirements(tender_id)

    # 后台重新解析
    background_tasks.add_task(tender_service.parse_tender, tender_id)

    return success_response(
        data={"tender_id": tender_id, "status": "parsing"},
        message="重新解析任务已提交",
    )


@router.get("", summary="标书列表")
async def list_tenders(
    search: str = "",
    status: str = "",
    region: str = "",
) -> dict:
    """获取标书列表（按上传时间倒序），支持搜索和筛选。

    Args:
        search: 按标题/文件名模糊搜索。
        status: 按状态筛选。
        region: 按地区筛选（省份名模糊匹配，如"江苏"匹配"江苏省南京市"）。

    Returns:
        统一响应，data 为标书列表。
    """
    try:
        tenders = await tender_service.list_tenders(
            search=search, status=status, region=region,
        )
        return success_response(data=[t.model_dump() for t in tenders])
    except Exception as e:
        logger.error("获取标书列表失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取列表失败: {str(e)}")


@router.get("/{tender_id}", summary="标书详情")
async def get_tender(tender_id: int) -> dict:
    """获取标书详情（含要求列表）。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为 ``{"tender": {...}, "requirements": [...]}``。
    """
    tender = await tender_service.get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    requirements = await tender_service.get_tender_requirements(tender_id)
    return success_response(
        data={
            "tender": tender.model_dump(),
            "requirements": [r.model_dump() for r in requirements],
        }
    )


@router.get("/{tender_id}/requirements", summary="标书要求列表")
async def get_tender_requirements(tender_id: int) -> dict:
    """获取标书的所有资质要求列表。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为要求列表。
    """
    tender = await tender_service.get_tender(tender_id)
    if tender is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")

    requirements = await tender_service.get_tender_requirements(tender_id)
    return success_response(data=[r.model_dump() for r in requirements])


@router.put("/{tender_id}/requirements/{requirement_id}", summary="修改标书要求")
async def update_requirement(
    tender_id: int,
    requirement_id: int,
    req: TenderRequirementUpdate,
) -> dict:
    if req.review_status not in (None, "pending", "confirmed"):
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "无效的解析确认状态")
    result = await tender_service.update_requirement(tender_id, requirement_id, req)
    if result is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "要求不存在")
    return success_response(data=result.model_dump(), message="要求已更新")


@router.post("/{tender_id}/requirements", summary="手动新增标书要求")
async def create_requirement(
    tender_id: int,
    req: TenderRequirementUpdate,
) -> dict:
    if not req.title or not req.content:
        return error_response(
            ErrorCode.PARAM_VALIDATION_FAILED,
            "标题和要求内容不能为空",
        )
    result = await tender_service.create_requirement(tender_id, req)
    return success_response(data=result.model_dump(), message="要求已新增")


@router.delete("/{tender_id}/requirements/{requirement_id}", summary="删除标书要求")
async def delete_requirement(tender_id: int, requirement_id: int) -> dict:
    deleted = await tender_service.delete_requirement(tender_id, requirement_id)
    if not deleted:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "要求不存在")
    return success_response(data={"deleted": True}, message="要求已删除")


@router.post("/{tender_id}/requirements/batch-status", summary="批量确认标书要求")
async def batch_requirement_status(
    tender_id: int,
    req: TenderRequirementBatchStatus,
) -> dict:
    if req.review_status not in ("pending", "confirmed"):
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "无效的解析确认状态")
    count = await tender_service.batch_update_requirement_status(
        tender_id, req.requirement_ids, req.review_status
    )
    return success_response(data={"updated": count}, message="状态已更新")


@router.post("/{tender_id}/requirements/batch-delete", summary="批量删除标书要求")
async def batch_delete_requirements(
    tender_id: int,
    req: TenderRequirementBatchDelete,
) -> dict:
    count = await tender_service.batch_delete_requirements(
        tender_id, req.requirement_ids
    )
    return success_response(data={"deleted": count}, message="要求已删除")


@router.get("/{tender_id}/pdf", summary="读取标书 PDF")
async def get_tender_pdf(tender_id: int):
    pdf_path = await tender_service.get_tender_pdf_path(tender_id)
    if pdf_path is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "PDF 文件不存在")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"tender-{tender_id}.pdf",
        content_disposition_type="inline",
    )


@router.get("/{tender_id}/status", summary="解析进度")
async def get_tender_status(tender_id: int) -> dict:
    """获取标书解析进度。

    前端轮询此端点获取解析状态变化。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为 ``{"tender_id": int, "status": str, "total_pages": int}``。
    """
    status = await tender_service.get_tender_status(tender_id)
    if status is None:
        return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")
    return success_response(data=status)


@router.delete("/{tender_id}", summary="删除标书")
async def delete_tender(tender_id: int) -> dict:
    """删除标书及其关联数据（要求、匹配结果、文件）。

    级联删除 tender_requirements / match_results / fill_templates 中的关联记录，
    同时删除磁盘上的原始文件和转换后的 PDF。

    Args:
        tender_id: 标书 ID。

    Returns:
        统一响应，data 为 ``{"deleted": bool}``。
    """
    try:
        deleted = await tender_service.delete_tender(tender_id)
        if not deleted:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, f"标书 {tender_id} 不存在")
        logger.info("删除标书成功: id=%s", tender_id)
        return success_response(data={"deleted": True}, message="标书已删除")
    except Exception as e:
        logger.error("删除标书失败: id=%s, error=%s", tender_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"删除失败: {str(e)}")
