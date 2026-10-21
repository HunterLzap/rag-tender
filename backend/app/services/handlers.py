import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    ChecklistItem,
    Document,
    Job,
    Page,
)
from app.services.analysis import decide_run
from app.services.checklist import build_checklist
from app.services.extraction import extract_requirements_for_run
from app.services.ir_persistence import persist_parsed_document, rebuild_section_tree
from app.services.jobs import mark_progress, register_handler
from app.services.parser import parse_document
from app.services.vision import transcribe_scanned_page

logger = logging.getLogger(__name__)


async def parse_document_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    document_id = job.payload["document_id"]
    document = await session.get(Document, document_id)
    if document is None:
        raise RuntimeError("文档不存在")
    await mark_progress(session, job.id, progress=5, stage="正在解析文档")
    parsed = await asyncio.to_thread(
        parse_document,
        __import__("pathlib").Path(document.storage_path),
        get_settings().rendered_dir,
    )
    await mark_progress(session, job.id, progress=65, stage="正在保存文档结构")
    revision = await persist_parsed_document(session, document, parsed)
    page_records = (
        await session.execute(
            select(Page)
            .where(Page.revision_id == revision.id)
            .order_by(Page.page_index)
        )
    ).scalars().all()
    for page_record in page_records:
        if page_record.parse_mode != "needs_vision" or not page_record.render_path:
            continue
        try:
            text = await transcribe_scanned_page(
                session,
                __import__("pathlib").Path(page_record.render_path),
                job_id=job.id,
            )
            page_record.text = text
            page_record.parse_mode = "vision"
            page_record.quality_flags = [
                flag for flag in page_record.quality_flags if flag != "vision_pending"
            ]
        except RuntimeError as exc:
            logger.warning("vision transcription skipped: %s", exc)
            page_record.quality_flags = [
                *page_record.quality_flags,
                "vision_failed",
            ]
    await session.flush()
    await rebuild_section_tree(session, revision.id)
    document.metadata_json = {
        **(document.metadata_json or {}),
        "last_parsed_revision": revision.id,
    }
    await session.commit()
    await mark_progress(session, job.id, progress=95, stage="文档解析完成")
    return {
        "document_id": document.id,
        "revision_id": revision.id,
        "page_count": len(parsed.pages),
    }


async def analyze_project_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    run_id = job.payload["run_id"]
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise RuntimeError("分析任务不存在")
    await mark_progress(session, job.id, progress=10, stage="准备分析")
    run.status = AnalysisStatus.RUNNING
    run.stage = "extracting_requirements"
    await session.commit()

    async def update_progress(current: int, total: int) -> None:
        await mark_progress(
            session,
            job.id,
            progress=10 + int(current / max(total, 1) * 50),
            stage=f"提取要求 {current}/{total}",
        )

    count, notes = await extract_requirements_for_run(
        session,
        run,
        job_id=job.id,
        progress_cb=update_progress,
        config_id=job.payload.get("model_config_id"),
    )
    await mark_progress(session, job.id, progress=70, stage="执行判定")
    counts = await decide_run(
        session,
        run,
        job_id=job.id,
        config_id=job.payload.get("model_config_id"),
    )
    run.progress = 90
    run.status = AnalysisStatus.NEEDS_REVIEW if notes else run.status
    await build_checklist(session, run.id)
    run.progress = 95
    open_items = (
        await session.execute(
            select(ChecklistItem).where(
                ChecklistItem.run_id == run.id,
                ChecklistItem.completed.is_(False),
            )
        )
    ).scalars().all()
    run.status = (
        AnalysisStatus.NEEDS_REVIEW if notes or open_items else AnalysisStatus.COMPLETED
    )
    await session.commit()
    return {
        "run_id": run.id,
        "requirement_count": count,
        "decision_counts": counts,
        "coverage_notes": notes,
    }


register_handler("parse_document", parse_document_job)
register_handler("analyze_project", analyze_project_job)
