import asyncio
import logging
import signal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import create_schema, get_engine, utcnow
from app.models import AnalysisRun, AnalysisStatus, Job, JobStatus
from app.services import handlers  # noqa: F401
from app.services.jobs import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def fail_running_jobs(session: AsyncSession) -> None:
    jobs = (
        await session.execute(select(Job).where(Job.status == JobStatus.RUNNING))
    ).scalars().all()
    exhausted = [job for job in jobs if job.attempts >= job.max_attempts]
    recoverable = [job for job in jobs if job.attempts < job.max_attempts]
    now = utcnow()

    for job in exhausted:
        job.status = JobStatus.FAILED
        job.stage = "失败：超过最大重试次数"
        job.lease_owner = None
        job.lease_until = None
        job.finished_at = now
        job.updated_at = now
        run_id = job.payload.get("run_id") if job.kind == "analyze_project" else None
        run = await session.get(AnalysisRun, run_id) if run_id else None
        if run is not None:
            run.status = AnalysisStatus.FAILED
            run.progress = 100
            run.stage = "analysis_failed"
            run.error = job.error or "任务超过最大重试次数"
            run.finished_at = now

    for job in recoverable:
        job.status = JobStatus.QUEUED
        job.stage = "worker 启动后恢复任务"
        job.lease_owner = None
        job.lease_until = None
        job.finished_at = None
        job.updated_at = now

    await session.commit()


async def main() -> None:
    settings = get_settings()
    if settings.auto_create_schema:
        await create_schema()
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        await fail_running_jobs(session)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass
    await worker_loop(stop_event, settings.worker_poll_seconds, settings.job_lease_seconds)


if __name__ == "__main__":
    asyncio.run(main())
