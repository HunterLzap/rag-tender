from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.management import _require_idle
from app.config import get_settings
from app.db import get_session
from app.models import Document, Project
from app.services.freshness import mark_project_stale
from app.services.interpretation import read_tender, reading_markdown
from app.services.pipeline import queue_document_processing

router = APIRouter()


@router.get("/projects/{project_id}/interpretation")
async def get_interpretation(project_id: str, session: AsyncSession = Depends(get_session)):
    if await session.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")
    return await read_tender(session, project_id)


@router.post("/projects/{project_id}/interpretation", status_code=202)
async def interpret_project(project_id: str, session: AsyncSession = Depends(get_session)):
    if await session.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")
    if not get_settings().live_model_calls:
        raise HTTPException(409, "模型服务暂不可用，请稍后解读")
    await _require_idle(session, project_id)
    documents = list((await session.execute(select(Document).where(
        Document.project_id == project_id, Document.role.in_(["tender", "addendum", "qa"]),
    ))).scalars())
    if not documents:
        raise HTTPException(409, "请先上传招标文件")
    if any(not d.current_revision_id or d.metadata_json.get("parse_status") in {
        "queued", "running", "failed", "canceled",
    } for d in documents):
        raise HTTPException(409, "请先完成招标文件解析")
    for document in documents:
        if document.metadata_json.get("ai_status") in {"queued", "running"}:
            continue
        document.metadata_json = {
            **document.metadata_json,
            "text_version": document.metadata_json.get("text_version", 0) + 1,
        }
        await queue_document_processing(session, document)
    await mark_project_stale(session, project_id)
    await session.commit()
    return await read_tender(session, project_id)


@router.get("/projects/{project_id}/interpretation/export")
async def export_interpretation(project_id: str, session: AsyncSession = Depends(get_session)):
    reading = await get_interpretation(project_id, session)
    return Response(reading_markdown(reading), media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote('标书解读.md')}",
    })
