from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisRun,
    AnalysisStatus,
    Decision,
    FillPlan,
    FillSuggestion,
    FillTarget,
    SuggestionStatus,
)


async def mark_project_stale(session: AsyncSession, project_id: str) -> None:
    run_ids = list((await session.execute(select(AnalysisRun.id).where(
        AnalysisRun.project_id == project_id,
        AnalysisRun.status.in_([
            AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW, AnalysisStatus.STALE,
            AnalysisStatus.FAILED,
        ]),
    ))).scalars())
    if not run_ids:
        return
    await session.execute(
        update(Decision).where(Decision.run_id.in_(run_ids)).values(stale=True)
    )
    await session.execute(
        update(AnalysisRun).where(
            AnalysisRun.id.in_(run_ids), AnalysisRun.status != AnalysisStatus.FAILED,
        ).values(status=AnalysisStatus.STALE)
    )
    await invalidate_fill_plans(session, run_ids)
    from app.services.checklist import build_checklist

    for run_id in run_ids:
        await build_checklist(session, run_id)


async def invalidate_fill_plans(session: AsyncSession, run_ids: list[str]) -> None:
    """Keep saved values, but reopen every human decision based on changed inputs."""
    plan_ids = select(FillPlan.id).where(FillPlan.run_id.in_(run_ids))
    target_ids = select(FillTarget.id).where(FillTarget.plan_id.in_(plan_ids))
    await session.execute(
        update(FillSuggestion).where(
            FillSuggestion.target_id.in_(target_ids),
            FillSuggestion.status.in_([
                SuggestionStatus.ACCEPTED, SuggestionStatus.EDITED, SuggestionStatus.REJECTED,
            ]),
        ).values(status=SuggestionStatus.PROPOSED)
    )
    await session.execute(
        update(FillPlan).where(
            FillPlan.run_id.in_(run_ids), FillPlan.status.notin_(["queued", "drafting"]),
        ).values(status="stale")
    )
