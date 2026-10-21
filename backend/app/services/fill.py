import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    AnnotationAsset,
    Block,
    Document,
    FillPlan,
    FillSlot,
    FillSuggestion,
    FillTarget,
    FillTargetKind,
    Page,
    Requirement,
    ResponseValue,
    SuggestionStatus,
    TableCell,
)


@dataclass(frozen=True)
class SlotCandidate:
    page: Page
    block: Block | None
    label: str
    bbox: list[float]
    kind: FillTargetKind


async def detect_fill_slots(
    session: AsyncSession, document: Document
) -> list[FillSlot]:
    if not document.current_revision_id:
        return []
    pages = (
        await session.execute(
            select(Page)
            .where(Page.revision_id == document.current_revision_id)
            .order_by(Page.page_index)
        )
    ).scalars().all()
    slots: list[FillSlot] = []
    for page in pages:
        blocks = (
            await session.execute(
                select(Block).where(Block.page_id == page.id).order_by(Block.reading_order)
            )
        ).scalars().all()
        for block in blocks:
            if block.kind != "table":
                continue
            cells = (
                await session.execute(
                    select(TableCell)
                    .where(TableCell.block_id == block.id)
                    .order_by(TableCell.row_index, TableCell.col_index)
                )
            ).scalars().all()
            if not cells:
                continue
            max_row = max(cell.row_index for cell in cells)
            max_col = max(cell.col_index for cell in cells)
            occupied = {(cell.row_index, cell.col_index) for cell in cells}
            header = [""] * (max_col + 1)
            for cell in cells:
                if cell.row_index == 0:
                    header[cell.col_index] = cell.text.strip()
            header_labels = [value for value in header if value]
            if len(header_labels) < 2:
                continue
            for cell in cells:
                if cell.row_index == 0:
                    continue
                label = header[cell.col_index] if cell.col_index < len(header) else "待填写"
                if label and cell.text.strip() and cell.text.strip() != label:
                    # This is a populated row, not an empty input slot.
                    continue
                slot = FillSlot(
                    template_revision_id=document.current_revision_id,
                    page_id=page.id,
                    block_id=block.id,
                    kind=FillTargetKind.TABLE_CELL,
                    label=label,
                    locator={
                        "kind": "table_cell",
                        "row": cell.row_index,
                        "col": cell.col_index,
                        "max_row": max(max_row, 2),
                        "max_col": max_col,
                        **cell.native_locator,
                    },
                    bbox_json=[cell.x0, cell.y0, cell.x1, cell.y1],
                    value_schema={"type": "string"},
                )
                session.add(slot)
                slots.append(slot)
            if max_row == 0:
                synthetic_rows = 2
                for row in range(1, synthetic_rows + 1):
                    for col in range(max_col + 1):
                        label = header[col] if col < len(header) and header[col] else "待填写"
                        slot = FillSlot(
                            template_revision_id=document.current_revision_id,
                            page_id=page.id,
                            block_id=block.id,
                            kind=FillTargetKind.TABLE_CELL,
                            label=label,
                            locator={
                                "kind": "table_cell",
                                "row": row,
                                "col": col,
                                "max_row": synthetic_rows,
                                "max_col": max_col,
                                "synthetic": True,
                            },
                            bbox_json=_synthetic_row_bbox(block, synthetic_rows, row, col, max_col),
                            value_schema={"type": "string"},
                        )
                        session.add(slot)
                        slots.append(slot)
            for row in range(1, max_row + 1):
                for col in range(max_col + 1):
                    if (row, col) in occupied:
                        continue
                    label = header[col] if col < len(header) and header[col] else "待填写"
                    slot = FillSlot(
                        template_revision_id=document.current_revision_id,
                        page_id=page.id,
                        block_id=block.id,
                        kind=FillTargetKind.TABLE_CELL,
                        label=label,
                        locator={
                            "kind": "table_cell",
                            "row": row,
                            "col": col,
                            "max_row": max_row,
                            "max_col": max_col,
                        },
                        bbox_json=block_bbox_for_empty_cell(block, cells, row, col),
                        value_schema={"type": "string"},
                    )
                    session.add(slot)
                    slots.append(slot)
        for block in blocks:
            if block.kind != "line":
                continue
            match = re.search(r"([^:：]{2,30})[:：]\s*[_—\-]{2,}", block.text)
            if not match:
                continue
            slot = FillSlot(
                template_revision_id=document.current_revision_id,
                page_id=page.id,
                block_id=block.id,
                kind=FillTargetKind.TEXT_BOX,
                label=match.group(1).strip(),
                locator={"kind": "text_box", "block_id": block.id},
                bbox_json=[block.x0, block.y0, block.x1, block.y1],
                value_schema={"type": "string"},
            )
            session.add(slot)
            slots.append(slot)
    await session.flush()
    return slots


def _synthetic_row_bbox(
    block: Block,
    rows: int,
    row: int,
    col: int,
    max_col: int,
) -> list[float]:
    row_height = 22.0
    col_width = (block.x1 - block.x0) / (max_col + 1)
    top = block.y1 + (row - 1) * row_height
    return [
        block.x0 + col * col_width,
        top,
        block.x0 + (col + 1) * col_width,
        top + row_height,
    ]


def block_bbox_for_empty_cell(
    block: Block,
    cells: list[TableCell],
    row: int,
    col: int,
) -> list[float]:
    max_col = max(cell.col_index for cell in cells)
    if max_col < 0:
        return [block.x0, block.y0, block.x1, block.y1]
    width = (block.x1 - block.x0) / (max_col + 1)
    max_row = max(cell.row_index for cell in cells)
    height = (block.y1 - block.y0) / max(max_row + 1, 1)
    return [
        block.x0 + col * width,
        block.y0 + row * height,
        block.x0 + (col + 1) * width,
        block.y0 + (row + 1) * height,
    ]


async def create_fill_plan(
    session: AsyncSession,
    *,
    run_id: str,
    project_id: str,
    template_document: Document,
) -> FillPlan:
    plan = FillPlan(
        run_id=run_id,
        document_id=template_document.id,
        template_revision_id=template_document.current_revision_id,
        status="draft",
    )
    session.add(plan)
    await session.flush()

    slots = (
        await session.execute(
            select(FillSlot).where(
                FillSlot.template_revision_id == template_document.current_revision_id
            )
        )
    ).scalars().all()
    requirements = (
        await session.execute(
            select(Requirement).where(Requirement.run_id == run_id)
        )
    ).scalars().all()
    response_values = (
        await session.execute(
            select(ResponseValue).where(ResponseValue.project_id == project_id)
        )
    ).scalars().all()
    for slot in slots:
        suggestion = _match_response_value(slot.label, response_values)
        related = _match_requirement(slot.label, requirements)
        target = FillTarget(
            plan_id=plan.id,
            page_id=slot.page_id,
            block_id=slot.block_id,
            table_cell_id=slot.table_cell_id,
            fill_slot_id=slot.id,
            kind=slot.kind,
            label=slot.label,
            bbox_json=slot.bbox_json,
            requirement_id=related.id if related else None,
        )
        session.add(target)
        await session.flush()
        if suggestion:
            session.add(
                FillSuggestion(
                    target_id=target.id,
                    value=suggestion.value_text,
                    rationale=f"来自项目响应值「{suggestion.label}」",
                    confidence=1.0,
                    status=SuggestionStatus.PROPOSED,
                    evidence_ids=suggestion.evidence_ids,
                )
            )
        else:
            if related:
                session.add(
                    FillSuggestion(
                        target_id=target.id,
                        value=None,
                        rationale=f"对应要求：{related.title}；尚无可填写值",
                        confidence=0.4,
                        status=SuggestionStatus.MISSING_EVIDENCE,
                        evidence_ids=[],
                    )
                )
    await session.flush()
    return plan


async def rebuild_fill_plan(
    session: AsyncSession,
    plan: FillPlan,
    *,
    project_id: str,
) -> FillPlan:
    targets = (
        await session.execute(
            select(FillTarget)
            .options(selectinload(FillTarget.suggestions))
            .where(FillTarget.plan_id == plan.id)
        )
    ).scalars().all()
    reviewed = {
        target.fill_slot_id: target.suggestions[0]
        for target in targets
        if target.fill_slot_id and target.suggestions
        and target.suggestions[0].status
        in {SuggestionStatus.ACCEPTED, SuggestionStatus.EDITED}
    }

    for target in targets:
        for suggestion in target.suggestions:
            await session.delete(suggestion)
    await session.flush()
    for target in targets:
        await session.delete(target)
    await session.flush()

    rebuilt = await create_fill_plan(
        session,
        run_id=plan.run_id,
        project_id=project_id,
        template_document=await session.get(Document, plan.document_id),
    )
    refreshed = (
        await session.execute(
            select(FillTarget)
            .options(selectinload(FillTarget.suggestions))
            .where(FillTarget.plan_id == rebuilt.id)
        )
    ).scalars().all()
    for target in refreshed:
        suggestion = reviewed.get(target.fill_slot_id)
        if suggestion is None:
            continue
        target.suggestions.clear()
        session.add(
            FillSuggestion(
                target_id=target.id,
                value=suggestion.value,
                rationale=suggestion.rationale,
                confidence=suggestion.confidence,
                status=suggestion.status,
                evidence_ids=suggestion.evidence_ids,
                reviewed_by=suggestion.reviewed_by,
                reviewed_at=suggestion.reviewed_at,
                review_note=suggestion.review_note,
            )
        )
    await session.flush()
    return rebuilt


async def render_annotations(
    session: AsyncSession, plan: FillPlan
) -> list[AnnotationAsset]:
    settings = get_settings()
    output_dir = settings.exports_dir / plan.id
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = (
        await session.execute(
            select(FillTarget)
            .options(selectinload(FillTarget.suggestions))
            .where(FillTarget.plan_id == plan.id)
            .order_by(FillTarget.created_at)
        )
    ).scalars().all()
    by_page: dict[str, list[FillTarget]] = {}
    for target in targets:
        by_page.setdefault(target.page_id, []).append(target)
    assets: list[AnnotationAsset] = []
    for page_id, page_targets in by_page.items():
        page = await session.get(Page, page_id)
        if page is None or not page.render_path:
            continue
        source = Path(page.render_path)
        if not source.exists():
            continue
        source_image = Image.open(source).convert("RGB")
        footer_height = 56
        image = Image.new(
            "RGB", (source_image.width, source_image.height + footer_height), (255, 253, 247)
        )
        image.paste(source_image, (0, 0))
        draw = ImageDraw.Draw(image)
        scale_x = image.width / page.width
        scale_y = image.height / page.height
        annotations = []
        for index, target in enumerate(page_targets, start=1):
            x0, y0, x1, y1 = target.bbox_json
            box = (x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y)
            draw.rectangle(box, outline=(210, 50, 30), width=4)
            draw.ellipse((box[0] - 4, box[1] - 20, box[0] + 26, box[1] + 10), fill=(210, 50, 30))
            draw.text(
                (box[0] + 5, box[1] - 18),
                str(index),
                fill="white",
                font=_annotation_font(),
            )
            suggestion = target.suggestions[0] if target.suggestions else None
            annotation = {
                "index": index,
                "target_id": target.id,
                "label": target.label,
                "value": suggestion.value if suggestion else None,
                "bbox": target.bbox_json,
            }
            annotations.append(annotation)
        per_column = max(1, (image.height - 40) // max(len(annotations), 1))
        for index, annotation in enumerate(annotations):
            legend_top = 20 + index * per_column
            text = (
                f"{annotation['index']}. {annotation['label']}: "
                f"{annotation['value'] or '待填写'}"
            )
            draw.rectangle(
                (image.width - 430, legend_top, image.width - 20, legend_top + 42),
                fill=(255, 253, 247),
                outline=(183, 67, 43),
            )
            fitted = _fit_text(text, _annotation_font(), 390)
            draw.text(
                (image.width - 415, legend_top + 11),
                fitted,
                fill=(36, 32, 26),
                font=_annotation_font(),
            )
        draw.text(
            (20, image.height - 38),
            f"投标响应工作台 · 第 {page.page_index + 1} 页 · {len(annotations)} 个填写位置",
            fill=(104, 95, 82),
            font=_annotation_font(),
        )
        target_path = output_dir / f"page-{page.page_index + 1:04d}-annotated.png"
        image.save(target_path)
        asset = AnnotationAsset(
            plan_id=plan.id,
            page_id=page.id,
            kind="page",
            path=str(target_path),
            width=image.width,
            height=image.height,
            annotations=annotations,
        )
        session.add(asset)
        assets.append(asset)
    await session.flush()
    return assets


def _annotation_font():
    from pathlib import Path

    from PIL import ImageFont

    for candidate in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, 20)
    return ImageFont.load_default()


def _fit_text(text: str, font, max_width: int) -> str:
    if font.getlength(text) <= max_width:
        return text
    ellipsis = "..."
    while text and font.getlength(text + ellipsis) > max_width:
        text = text[:-1]
    return text + ellipsis


def _match_response_value(label: str, values: list[ResponseValue]) -> ResponseValue | None:
    normalized = re.sub(r"\s+", "", label)
    for value in values:
        if value.key in normalized or normalized in value.label:
            return value
    return None


def _match_requirement(label: str, requirements: list[Requirement]) -> Requirement | None:
    normalized = re.sub(r"\s+", "", label)
    for requirement in requirements:
        if normalized in requirement.title or requirement.title in normalized:
            return requirement
    return None
