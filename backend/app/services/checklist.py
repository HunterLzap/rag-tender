from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AnalysisRun,
    AnalysisStatus,
    ChecklistItem,
    CheckSeverity,
    Decision,
    DecisionStatus,
    FillPlan,
    FillSuggestion,
    FillTarget,
    SuggestionStatus,
)


async def build_checklist(
    session: AsyncSession,
    run_id: str,
    *,
    reset_requirement_ids: set[str] | None = None,
) -> list[ChecklistItem]:
    stored = (
        await session.execute(select(ChecklistItem).where(ChecklistItem.run_id == run_id))
    ).scalars().all()
    existing = {item.title: item for item in stored if item.requirement_id is None}
    by_requirement = {
        item.requirement_id: item for item in stored
        if item.requirement_id and not item.title.startswith("确认填写：")
    }
    items: list[ChecklistItem] = list(stored)
    decisions = (
        await session.execute(
            select(Decision)
            .options(selectinload(Decision.requirement))
            .where(Decision.run_id == run_id)
        )
    ).scalars().all()
    for decision in decisions:
        requirement = decision.requirement
        title = requirement.title
        item = by_requirement.get(requirement.id)
        if not decision.stale and decision.status in {
            DecisionStatus.MET, DecisionStatus.NOT_APPLICABLE,
        }:
            if item:
                item.title = title
                item.detail = decision.summary
                item.completed = True
            continue
        if item is None:
            item = ChecklistItem(
                run_id=run_id,
                requirement_id=requirement.id,
                title=title,
                detail=decision.summary,
                severity=(
                    CheckSeverity.BLOCKER
                    if requirement.consequence == "rejection"
                    else CheckSeverity.WARNING
                ),
            )
            session.add(item)
            items.append(item)
            by_requirement[requirement.id] = item
        else:
            item.title = title
            item.detail = decision.summary
            if decision.stale or requirement.id in (reset_requirement_ids or set()):
                item.completed = False

    run = await session.get(AnalysisRun, run_id)
    for note in run.coverage_notes if run else []:
        title = f"核验提取范围：{note}"[:500]
        if title not in existing:
            item = ChecklistItem(
                run_id=run_id, title=title, detail=note, severity=CheckSeverity.WARNING
            )
            session.add(item)
            items.append(item)
            existing[title] = item

    fill_rows = (
        await session.execute(
            select(FillSuggestion, FillTarget)
            .join(FillTarget, FillTarget.id == FillSuggestion.target_id)
            .join(FillPlan, FillPlan.id == FillTarget.plan_id)
            .where(
                FillPlan.run_id == run_id,
            )
        )
    ).all()
    groups: dict[str, list] = {}
    for suggestion, target in fill_rows:
        title = f"确认填写：{target.label}"
        groups.setdefault(title, []).append((suggestion, target))
    for title, rows in groups.items():
        reviewed = all(
            suggestion.status in {
                SuggestionStatus.ACCEPTED,
                SuggestionStatus.EDITED,
                SuggestionStatus.REJECTED,
            }
            for suggestion, _target in rows
        )
        fill_existing = next((item for item in items if item.title == title), None)
        if fill_existing is None and not reviewed:
            suggestion, target = rows[0]
            item = ChecklistItem(
                run_id=run_id,
                requirement_id=target.requirement_id,
                title=title,
                detail=suggestion.rationale,
                severity=CheckSeverity.WARNING,
            )
            session.add(item)
            items.append(item)
            fill_existing = item
        if fill_existing is not None:
            fill_existing.completed = reviewed
    for item in list(items):
        if item.title.startswith("确认填写：") and item.title not in groups:
            await session.delete(item)
            items.remove(item)

    await session.flush()
    return items


async def mark_run_complete_if_ready(session: AsyncSession, run_id: str) -> None:
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        return
    open_items = (
        await session.execute(
            select(ChecklistItem).where(
                ChecklistItem.run_id == run_id,
                ChecklistItem.completed.is_(False),
            )
        )
    ).scalars().all()
    if run.status in {AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW} and not open_items:
        run.status = AnalysisStatus.COMPLETED
    elif run.status == AnalysisStatus.COMPLETED and open_items:
        run.status = AnalysisStatus.NEEDS_REVIEW
    if run.status in {AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW}:
        run.progress = 100
