import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.management import _require_document_idle, _require_idle
from app.api.routes import _load_fill_plan, _require_run_idle
from app.db import get_session, utcnow
from app.domain.rules import extract_condition
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    Block,
    Decision,
    DecisionStatus,
    Document,
    EvidenceItem,
    EvidenceStatus,
    FillPlan,
    FillSlot,
    FillSlotStatus,
    FillTarget,
    Page,
    Requirement,
    RequirementReviewStatus,
    RequirementStatus,
    SourceSpan,
    TableCell,
)
from app.schemas import (
    AnalysisRunRead,
    FillPlanRead,
    FillTargetCreate,
    FillTargetUpdate,
    PageRead,
    PageTextUpdate,
    RequirementCreate,
    RequirementRead,
)
from app.services.analysis import decide_run
from app.services.checklist import build_checklist, mark_run_complete_if_ready
from app.services.extraction import content_fingerprint
from app.services.fill import rebuild_fill_plan, render_annotations
from app.services.library import mark_document_stale
from app.services.pipeline import queue_document_processing
from app.storage import sha256_text

router = APIRouter()


@router.put("/pages/{page_id}/text", response_model=PageRead)
async def correct_page_text(
    page_id: str,
    payload: PageTextUpdate,
    session: AsyncSession = Depends(get_session),
):
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(404, "页面不存在")
    if not page.render_path:
        raise HTTPException(400, "此文件没有原页图片，请上传对应 PDF 后对照原页校正")
    document = await session.get(Document, page.document_id)
    await _require_document_idle(session, document)
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "请填写对照原页核实的文字")
    blocks = (await session.execute(select(Block).where(Block.page_id == page_id))).scalars().all()
    for block in blocks:
        block.kind = "historical_text"
    block = Block(
        page_id=page.id,
        kind="manual_text",
        reading_order=0,
        text=text,
        x0=0,
        y0=0,
        x1=page.width,
        y1=page.height,
        metadata_json={"coordinate_quality": "page", "manually_corrected": True},
    )
    session.add(block)
    await session.flush()
    session.add(
        SourceSpan(
            document_id=document.id,
            revision_id=page.revision_id,
            page_id=page.id,
            block_id=block.id,
            char_start=0,
            char_end=len(text),
            quote=text,
            quote_hash=sha256_text(text),
            bbox_json=[0, 0, page.width, page.height],
        )
    )
    page.text = text
    page.parse_mode = "manual"
    page.quality_flags = ["manual_transcription", "page_coordinates_only"]
    review_pages = [
        number
        for number in (document.metadata_json or {}).get("pages_needing_review", [])
        if number != page.page_index + 1
    ]
    document.metadata_json = {
        **(document.metadata_json or {}),
        "pages_needing_review": review_pages,
        "parse_status": "needs_review" if review_pages else "completed",
        "text_version": (document.metadata_json or {}).get("text_version", 0) + 1,
    }
    extracted = (
        (
            await session.execute(
                select(EvidenceItem)
                .join(SourceSpan, SourceSpan.id == EvidenceItem.source_span_id)
                .where(
                    SourceSpan.document_id == document.id,
                    EvidenceItem.payload["extraction_method"].as_string() == "llm",
                )
            )
        )
        .scalars()
        .all()
    )
    for item in extracted:
        item.status = EvidenceStatus.ARCHIVED
    await mark_document_stale(session, document)
    await queue_document_processing(session, document)
    await session.commit()
    return page


@router.post(
    "/analysis-runs/{run_id}/requirements",
    response_model=RequirementRead,
    status_code=201,
)
async def add_requirement(
    run_id: str,
    payload: RequirementCreate,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析记录不存在")
    await _require_run_idle(session, run_id)
    await _require_idle(session, run.project_id)
    span = await session.get(SourceSpan, payload.source_span_id)
    document = await session.get(Document, span.document_id) if span else None
    if (
        document is None
        or document.project_id != run.project_id
        or document.role
        not in {
            "tender",
            "addendum",
            "qa",
        }
    ):
        raise HTTPException(400, "请选择当前项目招标、补遗或答疑文件的原文")
    requirement = Requirement(
        run_id=run.id,
        **payload.model_dump(exclude={"source_span_id", "title"}),
        title=payload.title.strip(),
        source_span_id=span.id,
        condition_json=extract_condition(payload.statement, payload.category),
        fingerprint=content_fingerprint(payload.category, payload.statement),
        status=RequirementStatus.CONFIRMED,
        review_status=RequirementReviewStatus.CONFIRMED,
        extraction_method="manual",
    )
    session.add(requirement)
    await session.flush()
    session.add(
        Decision(
            run_id=run.id,
            requirement_id=requirement.id,
            status=DecisionStatus.NEEDS_REVIEW,
            summary="人工补充要求，请对照原文和证据保存复核结论",
        )
    )
    if run.status != AnalysisStatus.STALE:
        run.status = AnalysisStatus.NEEDS_REVIEW
    await session.flush()
    await build_checklist(session, run.id)
    await session.commit()
    return (
        await session.execute(
            select(Requirement)
            .options(selectinload(Requirement.source_span))
            .where(Requirement.id == requirement.id)
        )
    ).scalar_one()


@router.post("/analysis-runs/{run_id}/recheck", response_model=AnalysisRunRead)
async def recheck_rules(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析记录不存在")
    await _require_run_idle(session, run_id)
    await _require_idle(session, run.project_id)
    if run.status in {AnalysisStatus.DRAFT, AnalysisStatus.RUNNING, AnalysisStatus.FAILED}:
        raise HTTPException(409, "请先完成要求提取，或新建人工核对工作台")
    current = (
        (
            await session.execute(
                select(Document).where(
                    Document.project_id == run.project_id,
                    Document.role.in_(["tender", "addendum", "qa"]),
                )
            )
        )
        .scalars()
        .all()
    )
    snapshot = {
        (item["document_id"], item["revision_id"], item.get("text_version", 0))
        for item in run.input_snapshot
        if item["document_id"] in {document.id for document in current}
    }
    if snapshot != {
        (
            document.id,
            document.current_revision_id,
            (document.metadata_json or {}).get("text_version", 0),
        )
        for document in current
    }:
        raise HTTPException(409, "招标原文已变化，请新建人工工作台或重新提取要求")
    await decide_run(session, run, use_model=False)
    requirement_ids = set(
        (
            await session.execute(select(Requirement.id).where(Requirement.run_id == run_id))
        ).scalars()
    )
    await build_checklist(session, run_id, reset_requirement_ids=requirement_ids)
    await mark_run_complete_if_ready(session, run_id)
    run.progress = 100
    await session.commit()
    return AnalysisRunRead(**run.__dict__, requirement_count=len(requirement_ids))


def _validate_bbox(bbox: list[float], page: Page) -> None:
    x0, y0, x1, y1 = bbox
    if not all(math.isfinite(value) for value in bbox) or not (
        0 <= x0 < x1 <= page.width and 0 <= y0 < y1 <= page.height
    ):
        raise HTTPException(400, "请在原页面内框选一个有效的填写区域")


async def _refresh_plan(session: AsyncSession, plan: FillPlan) -> FillPlanRead:
    await render_annotations(session, plan)
    await build_checklist(session, plan.run_id)
    await mark_run_complete_if_ready(session, plan.run_id)
    await session.commit()
    return await _load_fill_plan(session, plan.id)


async def _bind_slot_position(session: AsyncSession, slot: FillSlot, bbox: list[float]) -> None:
    # Rebind a manually moved/created field to its actual table row, or clear the old binding.
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    cells = list((await session.execute(
        select(TableCell).join(Block, Block.id == TableCell.block_id).where(
            Block.page_id == slot.page_id, Block.kind == "table",
            TableCell.x0 <= cx, TableCell.x1 > cx,
            TableCell.y0 <= cy, TableCell.y1 > cy,
        )
    )).scalars())
    cell = cells[0] if len(cells) == 1 else None
    slot.table_cell_id = cell.id if cell else None
    slot.block_id = cell.block_id if cell else None
    slot.locator = {
        "kind": "table_cell" if cell else "manual",
        "coordinate_quality": "manual",
        "reference_only": False,
        **({"row": cell.row_index, "col": cell.col_index} if cell else {}),
    }


@router.post("/fill-plans/{plan_id}/targets", response_model=FillPlanRead, status_code=201)
async def add_fill_target(
    plan_id: str,
    payload: FillTargetCreate,
    session: AsyncSession = Depends(get_session),
):
    plan = await session.get(FillPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "填写计划不存在")
    await _require_run_idle(session, plan.run_id)
    page = await session.get(Page, payload.page_id)
    if page is None or page.revision_id != plan.template_revision_id:
        raise HTTPException(400, "请选择当前投标模板的页面")
    _validate_bbox(payload.bbox, page)
    slot = FillSlot(
        template_revision_id=plan.template_revision_id,
        page_id=page.id,
        kind=payload.kind,
        label=payload.label.strip(),
        bbox_json=payload.bbox,
        status=FillSlotStatus.VERIFIED,
        locator={"kind": "manual", "coordinate_quality": "manual", "manually_created": True},
        value_schema={"type": "string"},
    )
    session.add(slot)
    await _bind_slot_position(session, slot, payload.bbox)
    await session.flush()
    run = await session.get(AnalysisRun, plan.run_id)
    await rebuild_fill_plan(session, plan, project_id=run.project_id)
    return await _refresh_plan(session, plan)


@router.patch("/fill-targets/{target_id}", response_model=FillPlanRead)
async def edit_fill_target(
    target_id: str,
    payload: FillTargetUpdate,
    session: AsyncSession = Depends(get_session),
):
    target = await session.get(FillTarget, target_id)
    if target is None:
        raise HTTPException(404, "填写位置不存在")
    plan = await session.get(FillPlan, target.plan_id)
    await _require_run_idle(session, plan.run_id)
    slot = await session.get(FillSlot, target.fill_slot_id) if target.fill_slot_id else None
    if payload.label is not None:
        target.label = payload.label.strip()
        if slot:
            slot.label = target.label
    if payload.bbox is not None:
        page = await session.get(Page, target.page_id)
        _validate_bbox(payload.bbox, page)
        target.bbox_json = payload.bbox
        if slot:
            slot.bbox_json = payload.bbox
            await _bind_slot_position(session, slot, payload.bbox)
            target.block_id = slot.block_id
            target.table_cell_id = slot.table_cell_id
            slot.status = FillSlotStatus.VERIFIED
    target.updated_at = utcnow()
    return await _refresh_plan(session, plan)


@router.delete("/fill-targets/{target_id}", response_model=FillPlanRead)
async def remove_fill_target(target_id: str, session: AsyncSession = Depends(get_session)):
    target = await session.get(FillTarget, target_id)
    if target is None:
        raise HTTPException(404, "填写位置不存在")
    plan = await session.get(FillPlan, target.plan_id)
    await _require_run_idle(session, plan.run_id)
    slot = await session.get(FillSlot, target.fill_slot_id) if target.fill_slot_id else None
    if slot:
        slot.status = FillSlotStatus.IGNORED
    await session.delete(target)
    await session.flush()
    return await _refresh_plan(session, plan)
