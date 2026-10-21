from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
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


async def build_checklist(session: AsyncSession, run_id: str) -> list[ChecklistItem]:
    existing = {
        item.title: item
        for item in (
            await session.execute(select(ChecklistItem).where(ChecklistItem.run_id == run_id))
        ).scalars().all()
    }
    items: list[ChecklistItem] = list(existing.values())
    decisions = (
        await session.execute(
            select(Decision)
            .options(selectinload(Decision.requirement))
            .where(
                Decision.run_id == run_id,
                Decision.status.in_(
                    [DecisionStatus.NOT_MET, DecisionStatus.NEEDS_REVIEW]
                ),
            )
        )
    ).scalars().all()
    for decision in decisions:
        requirement = decision.requirement
        title = requirement.title
        if title not in existing:
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
    reviewed_titles = {
        f"确认填写：{target.label}"
        for suggestion, target in fill_rows
        if suggestion.status
        in {
            SuggestionStatus.ACCEPTED,
            SuggestionStatus.EDITED,
            SuggestionStatus.REJECTED,
        }
    }
    for suggestion, target in fill_rows:
        title = f"确认填写：{target.label}"
        if title in existing:
            continue
        reviewed = suggestion.status in {
            SuggestionStatus.ACCEPTED,
            SuggestionStatus.EDITED,
            SuggestionStatus.REJECTED,
        }
        if not reviewed:
            item = ChecklistItem(
                run_id=run_id,
                requirement_id=target.requirement_id,
                title=title,
                detail=suggestion.rationale,
                severity=CheckSeverity.WARNING,
            )
            session.add(item)
            items.append(item)
    for item in items:
        if item.title in reviewed_titles:
            item.completed = True

    await session.flush()
    return items


async def mark_run_complete_if_ready(session: AsyncSession, run_id: str) -> None:
    from app.models import AnalysisRun

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
