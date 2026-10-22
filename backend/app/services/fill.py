import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
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
    FillSlotStatus,
    FillSuggestion,
    FillTarget,
    FillTargetKind,
    Page,
    Requirement,
    ResponseValue,
    SuggestionStatus,
    TableCell,
)


async def detect_fill_slots(session: AsyncSession, document: Document) -> list[FillSlot]:
    if not document.current_revision_id:
        return []
    existing = (
        (
            await session.execute(
                select(FillSlot).where(
                    FillSlot.template_revision_id == document.current_revision_id
                )
            )
        )
        .scalars()
        .all()
    )
    if existing:
        return list(existing)
    pages = (
        (
            await session.execute(
                select(Page)
                .where(Page.revision_id == document.current_revision_id)
                .order_by(Page.page_index)
            )
        )
        .scalars()
        .all()
    )
    slots: list[FillSlot] = []
    for page in pages:
        blocks = (
            (
                await session.execute(
                    select(Block).where(Block.page_id == page.id).order_by(Block.reading_order)
                )
            )
            .scalars()
            .all()
        )
        for block in blocks:
            if block.kind != "table":
                continue
            cells = (
                (
                    await session.execute(
                        select(TableCell)
                        .where(TableCell.block_id == block.id)
                        .order_by(TableCell.row_index, TableCell.col_index)
                    )
                )
                .scalars()
                .all()
            )
            if not cells:
                continue
            max_row = max(cell.row_index for cell in cells)
            max_col = max(cell.col_index for cell in cells)
            header = [""] * (max_col + 1)
            for cell in cells:
                if cell.row_index == 0:
                    for col in range(cell.col_index, cell.col_index + cell.col_span):
                        if col < len(header):
                            header[col] = cell.text.strip()
            header_labels = [value for value in header if value]
            for cell in cells:
                if not _is_placeholder(cell.text) or cell.native_locator.get("scan_has_content"):
                    continue
                label = header[cell.col_index] or (
                    f"表{(block.metadata_json or {}).get('table_index', 0) + 1}"
                    f" · 第{cell.row_index + 1}行第{cell.col_index + 1}列"
                )
                left = next(
                    (
                        other
                        for other in reversed(cells)
                        if other.row_index == cell.row_index
                        and other.col_index + other.col_span == cell.col_index
                        and not _is_placeholder(other.text)
                    ),
                    None,
                )
                if left and (
                    cell.row_index == 0 or max_col == 1 or left.text.rstrip().endswith((":", "："))
                ):
                    label = left.text.strip().rstrip(":：")
                slot = FillSlot(
                    template_revision_id=document.current_revision_id,
                    page_id=page.id,
                    block_id=block.id,
                    table_cell_id=cell.id,
                    kind=FillTargetKind.TABLE_CELL,
                    label=label,
                    locator={
                        "kind": "table_cell",
                        "row": cell.row_index,
                        "col": cell.col_index,
                        "max_row": max_row,
                        "max_col": max_col,
                        **cell.native_locator,
                    },
                    bbox_json=[cell.x0, cell.y0, cell.x1, cell.y1],
                    value_schema={"type": "string"},
                )
                session.add(slot)
                slots.append(slot)
            if (
                max_row == 0
                and len(header_labels) >= 2
                and all(not _is_placeholder(cell.text) for cell in cells)
            ):
                # The header is a reference only; no writable row was located.
                for cell in cells:
                    slot = FillSlot(
                        template_revision_id=document.current_revision_id,
                        page_id=page.id,
                        block_id=block.id,
                        kind=FillTargetKind.TABLE_CELL,
                        table_cell_id=cell.id,
                        label=cell.text.strip(),
                        locator={
                            "kind": "table_cell",
                            "row": cell.row_index,
                            "col": cell.col_index,
                            "reference_only": True,
                            "coordinate_quality": "header_only",
                        },
                        bbox_json=[cell.x0, cell.y0, cell.x1, cell.y1],
                        value_schema={"type": "string"},
                    )
                    session.add(slot)
                    slots.append(slot)
        for block in blocks:
            if block.kind not in {"line", "paragraph"}:
                continue
            for label, kind, start, end in _text_fields(block.text):
                slot = FillSlot(
                    template_revision_id=document.current_revision_id,
                    page_id=page.id,
                    block_id=block.id,
                    kind=kind,
                    label=label,
                    locator={
                        "kind": kind.value,
                        "block_id": block.id,
                        "char_start": start,
                        "char_end": end,
                        "coordinate_quality": "text_span",
                    },
                    bbox_json=_text_field_bbox(block, start, end),
                    value_schema={"type": "string"},
                )
                session.add(slot)
                slots.append(slot)
    await session.flush()
    return slots


def _is_placeholder(text: str) -> bool:
    return re.fullmatch(r"[\s_＿—－\-()（）]*", text) is not None


def _text_fields(text: str):
    patterns = (
        r"(?P<label>[^:：_＿—－()（）]{2,30}?)[:：]\s*"
        r"(?P<blank>[_＿—－\-]{2,}|[（(]\s*[)）])",
        r"(?P<label>[^:：_＿—－()（）]{2,30}?)(?P<blank>[（(]\s+[)）])",
    )
    occupied: list[tuple[int, int]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            occupied.append(match.span())
            label = match.group("label").strip()
            kind = FillTargetKind.DATE if "日期" in label else FillTargetKind.TEXT_BOX
            if any(word in label for word in ("盖章", "签字", "签名", "签章")):
                kind = FillTargetKind.SIGNATURE
            yield label, kind, *match.span("blank")
    for match in re.finditer(r"(?P<box>[□☐])\s*(?P<label>[^\s□☐]{1,30})", text):
        yield match.group("label"), FillTargetKind.CHECKBOX, *match.span("box")
    for match in re.finditer(r"[（(](?P<label>[^()（）]{0,15}(?:盖章|签字|签名|签章))[)）]", text):
        if not any(match.start() < end and match.end() > start for start, end in occupied):
            yield match.group("label"), FillTargetKind.SIGNATURE, *match.span()


def _text_field_bbox(block: Block, start: int, end: int) -> list[float]:
    words = (block.metadata_json or {}).get("word_spans", [])
    boxes = []
    for word in words:
        left, right = max(start, word["start"]), min(end, word["end"])
        if left >= right:
            continue
        x0, y0, x1, y1 = word["bbox"]
        width = (x1 - x0) / (word["end"] - word["start"])
        boxes.append(
            [x0 + (left - word["start"]) * width, y0, x0 + (right - word["start"]) * width, y1]
        )
    if boxes:
        return [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ]
    width = (block.x1 - block.x0) / max(len(block.text), 1)
    return [block.x0 + start * width, block.y0, block.x0 + end * width, block.y1]


async def create_fill_plan(
    session: AsyncSession,
    *,
    run_id: str,
    project_id: str,
    template_document: Document,
    plan: FillPlan | None = None,
) -> FillPlan:
    if plan is None:
        plan = FillPlan(
            run_id=run_id,
            document_id=template_document.id,
            template_revision_id=template_document.current_revision_id,
            status="draft",
        )
        session.add(plan)
        await session.flush()

    slots = (
        (
            await session.execute(
                select(FillSlot).where(
                    FillSlot.template_revision_id == template_document.current_revision_id,
                    FillSlot.status != FillSlotStatus.IGNORED,
                )
            )
        )
        .scalars()
        .all()
    )
    requirements = (
        (await session.execute(select(Requirement).where(Requirement.run_id == run_id)))
        .scalars()
        .all()
    )
    response_values = (
        (await session.execute(select(ResponseValue).where(ResponseValue.project_id == project_id)))
        .scalars()
        .all()
    )
    from app.services.requirement_versions import version_state

    replaced, conflicts = version_state(list(requirements))
    requirements = [item for item in requirements
                    if item.id not in replaced and item.id not in conflicts
                    and item.review_status != "rejected"]
    for slot in slots:
        repeated_table_label = slot.table_cell_id and sum(
            other.label == slot.label and other.block_id == slot.block_id for other in slots
        ) > 1
        suggestion = (
            None if repeated_table_label else _match_response_value(slot.label, response_values)
        )
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
                    source_refs=[
                        {
                            "response_value_id": suggestion.id,
                            "label": suggestion.label,
                            "value": suggestion.value_text,
                        }
                    ],
                )
            )
        else:
            rationale = (
                f"对应要求：{related.title}；请补充填写值及依据"
                if related
                else f"请补充「{slot.label}」的填写值及依据"
            )
            if slot.kind == FillTargetKind.SIGNATURE:
                rationale = "此处需人工签字或盖章，确认实际办理后再接受"
            session.add(
                FillSuggestion(
                    target_id=target.id,
                    value=None,
                    rationale=rationale,
                    confidence=None,
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
        (
            await session.execute(
                select(FillTarget)
                .options(selectinload(FillTarget.suggestions))
                .where(FillTarget.plan_id == plan.id)
            )
        )
        .scalars()
        .all()
    )
    reviewed = {
        target.fill_slot_id: target.suggestions[0]
        for target in targets
        if target.fill_slot_id
        and target.suggestions
        and (target.suggestions[0].reviewed_at is not None
             or target.suggestions[0].status
             in {SuggestionStatus.ACCEPTED, SuggestionStatus.EDITED, SuggestionStatus.REJECTED})
    }

    for target in targets:
        await session.delete(target)
    await session.flush()

    template_document = await session.get(Document, plan.document_id)
    plan.template_revision_id = template_document.current_revision_id
    await detect_fill_slots(session, template_document)
    rebuilt = await create_fill_plan(
        session,
        run_id=plan.run_id,
        project_id=project_id,
        template_document=template_document,
        plan=plan,
    )
    refreshed = (
        (
            await session.execute(
                select(FillTarget)
                .options(selectinload(FillTarget.suggestions))
                .where(FillTarget.plan_id == rebuilt.id)
            )
        )
        .scalars()
        .all()
    )
    for target in refreshed:
        suggestion = reviewed.get(target.fill_slot_id)
        if suggestion is None:
            continue
        target.suggestions.clear()
        target.suggestions.append(
            FillSuggestion(
                target_id=target.id,
                value=suggestion.value,
                rationale=suggestion.rationale,
                confidence=suggestion.confidence,
                status=suggestion.status,
                evidence_ids=suggestion.evidence_ids,
                source_refs=suggestion.source_refs,
                reviewed_by=suggestion.reviewed_by,
                reviewed_at=suggestion.reviewed_at,
                review_note=suggestion.review_note,
            )
        )
    await session.flush()
    return rebuilt


def suggestion_display_value(target: FillTarget, suggestion: FillSuggestion | None) -> str:
    if suggestion is None:
        return ""
    if suggestion.status == SuggestionStatus.REJECTED:
        return "未采用"
    if target.kind == FillTargetKind.SIGNATURE:
        return "已确认线下签章" if suggestion.status in {
            SuggestionStatus.ACCEPTED, SuggestionStatus.EDITED,
        } else ""
    return suggestion.value or ""


async def render_annotations(session: AsyncSession, plan: FillPlan) -> list[AnnotationAsset]:
    settings = get_settings()
    output_dir = settings.exports_dir / plan.id
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = (
        (
            await session.execute(
                select(FillTarget)
                .options(selectinload(FillTarget.suggestions))
                .where(FillTarget.plan_id == plan.id)
                .order_by(FillTarget.created_at)
            )
        )
        .scalars()
        .all()
    )
    slots = {
        slot.id: slot
        for slot in (
            await session.execute(
                select(FillSlot).where(FillSlot.template_revision_id == plan.template_revision_id)
            )
        ).scalars()
    }
    existing_assets = {
        asset.page_id: asset
        for asset in (
            await session.execute(select(AnnotationAsset).where(AnnotationAsset.plan_id == plan.id))
        ).scalars()
    }
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
        with Image.open(source) as original:
            source_image = original.convert("RGB")
        scale_x = source_image.width / page.width
        scale_y = source_image.height / page.height
        legend_width = 420
        footer_height = 56
        annotations = []
        for index, target in enumerate(page_targets, start=1):
            suggestion = target.suggestions[0] if target.suggestions else None
            slot = slots.get(target.fill_slot_id)
            annotation = {
                "index": index,
                "target_id": target.id,
                "label": target.label,
                "value": suggestion_display_value(target, suggestion),
                "status": suggestion.status.value if suggestion else "missing_evidence",
                "bbox": target.bbox_json,
                "reference_only": bool(slot and slot.locator.get("reference_only")),
                "coordinate_quality": (
                    slot.locator.get("coordinate_quality", "native") if slot else "native"
                ),
                "polygon": slot.locator.get("polygon") if slot else None,
            }
            annotations.append(annotation)
        legend_cards = []
        legend_height = 64
        for annotation in annotations:
            value = annotation["value"] or "待补充"
            if annotation["status"] == SuggestionStatus.REJECTED.value:
                value = "未采用"
            note = "\n仅识别到表头，需确认实际填写行" if annotation["reference_only"] else ""
            text = f"{annotation['index']}. {annotation['label']}\n{value}{note}"
            lines = _wrap_text(text, _annotation_font(), legend_width - 48)
            height = len(lines) * 28 + 24
            legend_cards.append((lines, height))
            legend_height += height + 12
        image = Image.new(
            "RGB",
            (
                source_image.width + legend_width,
                max(source_image.height, legend_height) + footer_height,
            ),
            (255, 253, 247),
        )
        image.paste(source_image, (0, 0))
        draw = ImageDraw.Draw(image)
        for target, annotation in zip(page_targets, annotations, strict=True):
            x0, y0, x1, y1 = target.bbox_json
            box = (
                max(0, x0 * scale_x),
                max(0, y0 * scale_y),
                min(source_image.width, x1 * scale_x),
                min(source_image.height, y1 * scale_y),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            if annotation["reference_only"]:
                draw.rectangle(box, outline=(158, 113, 35), width=2)
                continue
            rejected = annotation["status"] == SuggestionStatus.REJECTED.value
            color = (120, 116, 109) if rejected else (183, 67, 43)
            value = "未采用" if rejected else annotation["value"]
            if not value:
                value = "需人工签章" if target.kind == FillTargetKind.SIGNATURE else "待补充"
            polygon = annotation.get("polygon")
            if polygon:
                points = [(point[0] * scale_x, point[1] * scale_y) for point in polygon]
                _draw_scanned_value(image, points, value, color)
                draw.line([*points, points[0]], fill=color, width=2)
            else:
                draw.rectangle(box, fill=(255, 246, 222), outline=color, width=2)
                _draw_value(draw, box, value, color)
        legend_left = source_image.width
        draw.line((legend_left, 0, legend_left, image.height), fill=(222, 213, 197), width=2)
        draw.text(
            (legend_left + 20, 18),
            "填写建议 / 完整内容",
            fill=(183, 67, 43),
            font=_annotation_font(),
        )
        legend_top = 64
        for lines, height in legend_cards:
            draw.rectangle(
                (legend_left + 12, legend_top, image.width - 12, legend_top + height),
                fill=(255, 251, 240),
                outline=(222, 213, 197),
            )
            draw.multiline_text(
                (legend_left + 24, legend_top + 10),
                "\n".join(lines),
                fill=(36, 32, 26),
                font=_annotation_font(),
                spacing=8,
            )
            legend_top += height + 12
        draw.text(
            (20, image.height - 38),
            f"投标响应工作台 · 第 {page.page_index + 1} 页 · {len(annotations)} 个填写位置",
            fill=(104, 95, 82),
            font=_annotation_font(),
        )
        target_path = output_dir / f"page-{page.page_index + 1:04d}-annotated.png"
        image.save(target_path)
        asset = existing_assets.pop(page_id, None)
        if asset is None:
            asset = AnnotationAsset(plan_id=plan.id, page_id=page.id, kind="page")
        asset.path = str(target_path)
        asset.width = image.width
        asset.height = image.height
        asset.annotations = annotations
        session.add(asset)
        assets.append(asset)
    for asset in existing_assets.values():
        await session.delete(asset)
    await session.flush()
    return assets


@lru_cache(maxsize=24)
def _annotation_font(size: int = 20):
    for candidate in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, max_width: float) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            if current and font.getlength(current + char) > max_width:
                lines.append(current)
                current = ""
            current += char
        lines.append(current)
    return lines


def _draw_value(draw, box, value: str, color) -> None:
    padding = 4
    width, height = box[2] - box[0] - padding * 2, box[3] - box[1] - padding * 2
    if width < 6 or height < 6:
        return
    font = _annotation_font(10)
    for size in range(min(24, int(height)), 9, -1):
        font = _annotation_font(size)
        lines = _wrap_text(value, font, width)
        text_box = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=2)
        if text_box[3] - text_box[1] <= height:
            break
    else:
        lines = _wrap_text(value, font, width)
        line_height = font.getbbox("国Ag")[3] + 2
        lines = lines[: max(1, int(height // line_height))]
        lines[-1] = _fit_text(lines[-1] + "...", font, int(width))
    text = "\n".join(lines)
    text_box = draw.multiline_textbbox((0, 0), text, font=font, spacing=2)
    draw.multiline_text(
        (box[0] + padding, box[1] + padding - text_box[1]),
        text,
        font=font,
        fill=color,
        spacing=2,
    )


def _draw_scanned_value(image: Image.Image, points, value: str, color) -> None:
    origin, right, _, bottom = points
    width = math.dist(origin, right)
    height = math.dist(origin, bottom)
    layer = Image.new("RGB", (math.ceil(width), math.ceil(height)), (255, 246, 222))
    _draw_value(ImageDraw.Draw(layer), (0, 0, width, height), value, color)
    left, top = math.floor(min(p[0] for p in points)), math.floor(min(p[1] for p in points))
    size = (
        math.ceil(max(p[0] for p in points)) - left,
        math.ceil(max(p[1] for p in points)) - top,
    )
    ux, uy = (right[0] - origin[0]) / width, (right[1] - origin[1]) / width
    vx, vy = (bottom[0] - origin[0]) / height, (bottom[1] - origin[1]) / height
    # Rotate the value with the cell; paint only inside the original scan polygon.
    transform = (
        ux,
        uy,
        ux * (left - origin[0]) + uy * (top - origin[1]),
        vx,
        vy,
        vx * (left - origin[0]) + vy * (top - origin[1]),
    )
    rotated = layer.transform(
        size,
        Image.Transform.AFFINE,
        transform,
        Image.Resampling.BICUBIC,
        fillcolor=(255, 246, 222),
    )
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([(x - left, y - top) for x, y in points], fill=255)
    image.paste(rotated, (left, top), mask)


def _fit_text(text: str, font, max_width: int) -> str:
    if font.getlength(text) <= max_width:
        return text
    ellipsis = "..."
    while text and font.getlength(text + ellipsis) > max_width:
        text = text[:-1]
    return text + ellipsis


def _match_response_value(label: str, values: list[ResponseValue]) -> ResponseValue | None:
    normalized = re.sub(r"[\s:：]", "", label)
    if not normalized:
        return None
    exact = [
        value for value in values if normalized in {value.key, re.sub(r"[\s:：]", "", value.label)}
    ]
    if exact:
        return exact[0] if len(exact) == 1 else None
    candidates = [
        value
        for value in values
        if normalized in re.sub(r"\s+", "", value.label) or value.key in normalized
    ]
    return candidates[0] if len(candidates) == 1 else None


def _match_requirement(label: str, requirements: list[Requirement]) -> Requirement | None:
    normalized = re.sub(r"\s+", "", label)
    for requirement in requirements:
        if normalized in requirement.title or requirement.title in normalized:
            return requirement
    return None
