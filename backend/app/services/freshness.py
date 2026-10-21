from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, AnalysisStatus, Decision


async def mark_project_stale(session: AsyncSession, project_id: str) -> None:
    run_ids = select(AnalysisRun.id).where(
        AnalysisRun.project_id == project_id,
        AnalysisRun.status.in_([
            AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW, AnalysisStatus.STALE,
        ]),
    )
    await session.execute(
        update(Decision).where(Decision.run_id.in_(run_ids)).values(stale=True)
    )
    await session.execute(
        update(AnalysisRun).where(AnalysisRun.id.in_(run_ids)).values(status=AnalysisStatus.STALE)
    )
