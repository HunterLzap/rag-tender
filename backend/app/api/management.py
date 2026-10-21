from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import _document_read, _model_config_read
from app.db import get_session
from app.models import (
    AnalysisRun,
    Block,
    Document,
    EvidenceItem,
    FillPlan,
    Job,
    JobStatus,
    ModelConfig,
    Page,
    Project,
    Requirement,
    SourceSpan,
)
from app.schemas import (
    DocumentRead,
    DocumentUpdate,
    ModelConfigRead,
    ModelConfigUpdate,
    SourceSpanRead,
)
from app.security import encrypt_secret
from app.services.checklist import build_checklist, mark_run_complete_if_ready
from app.services.freshness import mark_project_stale
from app.services.jobs import enqueue
from app.services.library import mark_document_stale, mark_organization_stale
from app.services.pipeline import (
    queue_document_processing,
    resume_pending_documents,
    schedule_related_projects,
)

router = APIRouter()


async def _require_idle(session: AsyncSession, project_id: str | None) -> None:
    if project_id is None:
        return
    running = (
        await session.execute(
            select(Job.id)
            .where(
                Job.payload["project_id"].as_string() == project_id,
                Job.status == JobStatus.RUNNING,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if running:
        raise HTTPException(409, "项目有任务正在处理，请等待结束或取消任务后再操作")


async def _require_document_idle(session: AsyncSession, document: Document) -> None:
    await _require_idle(session, document.project_id)
    if not document.organization_id:
        return
    projects = select(Project.id).where(Project.organization_id == document.organization_id)
    running = (
        await session.execute(
            select(Job.id)
            .where(
                Job.status == JobStatus.RUNNING,
                or_(
                    Job.payload["document_id"].as_string() == document.id,
                    Job.payload["project_id"].as_string().in_(projects),
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if running:
        raise HTTPException(409, "企业材料或关联项目正在处理，请等待结束后再操作")


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, session: AsyncSession = Depends(get_session)):
    if await session.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")
    await _require_idle(session, project_id)
    await session.execute(delete(Job).where(Job.payload["project_id"].as_string() == project_id))
    await session.execute(delete(EvidenceItem).where(EvidenceItem.project_id == project_id))
    await session.execute(delete(Project).where(Project.id == project_id))
    await session.commit()


@router.get("/documents/{document_id}/file")
async def download_document(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None or not Path(document.storage_path).exists():
        raise HTTPException(404, "原文件不存在")
    return FileResponse(
        document.storage_path,
        filename=document.filename,
        media_type=document.content_type or "application/octet-stream",
    )


@router.patch("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: str, payload: DocumentUpdate, session: AsyncSession = Depends(get_session)
):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文档不存在")
    await _require_document_idle(session, document)
    if document.organization_id and payload.role not in {None, "evidence"}:
        raise HTTPException(400, "企业库文件用途为证明材料")
    data = payload.model_dump(exclude_unset=True)
    if data.get("role") and data["role"] != document.role:
        duplicate = (
            await session.execute(
                select(Document.id).where(
                    Document.project_id == document.project_id,
                    Document.sha256 == document.sha256,
                    Document.role == data["role"],
                    Document.id != document.id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(409, "同一文件已按该用途上传，请直接使用已有文件")
        await mark_document_stale(session, document)
    for key, value in data.items():
        setattr(document, key, value)
    if data.get("role"):
        await queue_document_processing(session, document)
    await session.commit()
    return _document_read(document)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文档不存在")
    await _require_document_idle(session, document)
    for model in (Requirement, *([] if document.organization_id else [EvidenceItem])):
        reference = (
            await session.execute(
                select(model.id)
                .join(SourceSpan, model.source_span_id == SourceSpan.id)
                .where(SourceSpan.document_id == document_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if reference:
            raise HTTPException(409, "该文件仍被分析记录或证据引用，请先删除相关记录再移除文件")
    if document.organization_id:
        evidence_ids = (
            select(EvidenceItem.id)
            .join(
                SourceSpan,
                SourceSpan.id == EvidenceItem.source_span_id,
            )
            .where(SourceSpan.document_id == document.id)
        )
        await session.execute(delete(EvidenceItem).where(EvidenceItem.id.in_(evidence_ids)))
    await mark_document_stale(session, document)
    await session.execute(delete(Job).where(Job.payload["document_id"].as_string() == document_id))
    affected_runs = list(
        (
            await session.execute(
                select(FillPlan.run_id).where(FillPlan.document_id == document_id)
            )
        ).scalars()
    )
    await session.execute(delete(Document).where(Document.id == document_id))
    for run_id in affected_runs:
        await build_checklist(session, run_id)
        await mark_run_complete_if_ready(session, run_id)
    await session.commit()
    await schedule_related_projects(session, document)
    await session.commit()


@router.get("/pages/{page_id}/source-spans", response_model=list[SourceSpanRead])
async def list_page_spans(page_id: str, session: AsyncSession = Depends(get_session)):
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(404, "页面不存在")
    document = await session.get(Document, page.document_id)
    spans = (
        (
            await session.execute(
                select(SourceSpan)
                .where(
                    SourceSpan.page_id == page_id,
                    SourceSpan.table_cell_id.is_(None),
                )
                .join(Block, Block.id == SourceSpan.block_id)
                .where(Block.kind != "historical_text")
                .order_by(SourceSpan.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        SourceSpanRead(
            **span.__dict__, page_index=page.page_index, document_filename=document.filename
        )
        for span in spans
    ]


@router.delete("/analysis-runs/{run_id}", status_code=204)
async def delete_analysis(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析记录不存在")
    await _require_idle(session, run.project_id)
    await session.execute(delete(Job).where(Job.payload["run_id"].as_string() == run_id))
    await session.execute(delete(AnalysisRun).where(AnalysisRun.id == run_id))
    await session.commit()


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(evidence_id: str, session: AsyncSession = Depends(get_session)):
    evidence = await session.get(EvidenceItem, evidence_id)
    if evidence is None:
        raise HTTPException(404, "证据不存在")
    if evidence.organization_id:
        await mark_organization_stale(session, evidence.organization_id)
    else:
        await mark_project_stale(session, evidence.project_id)
    await session.execute(delete(EvidenceItem).where(EvidenceItem.id == evidence_id))
    await schedule_related_projects(session, evidence)
    await session.commit()


@router.post("/documents/{document_id}/reparse", response_model=DocumentRead)
async def reparse_document(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文档不存在")
    await _require_document_idle(session, document)
    document.metadata_json = {
        **(document.metadata_json or {}),
        "parse_status": "queued",
        "parse_error": None,
        "ai_status": "pending",
        "ai_error": None,
    }
    await enqueue(
        session,
        "parse_document",
        {
            "document_id": document.id,
            "_dedupe_key": f"parse:{document.id}",
        },
    )
    await mark_document_stale(session, document)
    await session.commit()
    return _document_read(document)


@router.patch("/model-configs/{config_id}", response_model=ModelConfigRead)
async def update_model_config(
    config_id: str, payload: ModelConfigUpdate, session: AsyncSession = Depends(get_session)
):
    config = await session.get(ModelConfig, config_id)
    if config is None:
        raise HTTPException(404, "模型配置不存在")
    data = payload.model_dump(exclude_unset=True)
    key = data.pop("api_key", None)
    embedding_key = data.pop("embedding_api_key", None)
    if key:
        config.api_key_encrypted = encrypt_secret(key)
    if "embedding_api_key" in payload.model_fields_set:
        config.embedding_api_key_encrypted = (
            encrypt_secret(embedding_key) if embedding_key else None
        )
    if data.get("is_active"):
        await session.execute(
            update(ModelConfig).where(ModelConfig.id != config_id).values(is_active=False)
        )
    for field, value in data.items():
        setattr(config, field, value)
    await session.commit()
    await resume_pending_documents(session)
    return _model_config_read(config, "")


@router.delete("/model-configs/{config_id}", status_code=204)
async def delete_model_config(config_id: str, session: AsyncSession = Depends(get_session)):
    config = await session.get(ModelConfig, config_id)
    if config is None:
        raise HTTPException(404, "模型配置不存在")
    in_use = (
        await session.execute(
            select(Job.id)
            .where(
                Job.payload["model_config_id"].as_string() == config_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if in_use:
        raise HTTPException(409, "该配置仍被分析任务使用，请结束任务后再删除")
    await session.execute(delete(ModelConfig).where(ModelConfig.id == config_id))
    await session.commit()
