import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_engine, utcnow
from app.models import AnalysisRun, AnalysisStatus, Job, JobStatus

logger = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, Job], Awaitable[dict[str, Any] | None]]
_handlers: dict[str, Handler] = {}


def register_handler(kind: str, handler: Handler) -> None:
    _handlers[kind] = handler


async def enqueue(session: AsyncSession, kind: str, payload: dict[str, Any]) -> Job:
    if kind not in _handlers:
        from app.services import handlers  # noqa: F401
    if kind not in _handlers:
        raise ValueError(f"未注册任务类型: {kind}")
    dedupe_key = payload.get("_dedupe_key")
    if dedupe_key:
        existing = (
            await session.execute(
                select(Job).where(
                    Job.dedupe_key == dedupe_key,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
    job = Job(
        kind=kind,
        payload={key: value for key, value in payload.items() if key != "_dedupe_key"},
        dedupe_key=dedupe_key,
    )
    if kind == "parse_document":
        document = await session.get(
            __import__("app.models", fromlist=["Document"]).Document, payload["document_id"]
        )
        if document is not None:
            job.payload = {**job.payload, "project_id": document.project_id}
    elif kind == "analyze_project":
        run = await session.get(
            __import__("app.models", fromlist=["AnalysisRun"]).AnalysisRun,
            payload["run_id"],
        )
        if run is not None:
            job.payload = {**job.payload, "project_id": run.project_id}
    session.add(job)
    await session.flush()
    return job


async def claim_job(session: AsyncSession, worker_id: str, lease_seconds: int) -> Job | None:
    now = utcnow()
    candidate = (
        await session.execute(
            select(Job.id)
            .where(Job.status == JobStatus.QUEUED, Job.available_at <= now)
            .order_by(Job.available_at, Job.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if candidate is None:
        return None
    stmt = (
        update(Job)
        .where(
            Job.id == candidate,
            Job.status == JobStatus.QUEUED,
            Job.available_at <= now,
        )
        .values(
            status=JobStatus.RUNNING,
            lease_owner=worker_id,
            lease_until=now + timedelta(seconds=lease_seconds),
            attempts=Job.attempts + 1,
            started_at=case((Job.started_at.is_(None), now), else_=Job.started_at),
            stage="任务开始",
        )
        .returning(Job.id)
    )
    job_id = (await session.execute(stmt)).scalar_one_or_none()
    if job_id is None:
        return None
    await session.commit()
    return await session.get(Job, job_id)


async def recover_expired_jobs(session: AsyncSession) -> int:
    now = utcnow()
    result = await session.execute(
        update(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.lease_until.is_not(None),
            Job.lease_until < now,
        )
        .values(
            status=JobStatus.QUEUED,
            lease_owner=None,
            lease_until=None,
            stage="任务超时，等待重试",
            error="worker lease expired",
        )
    )
    await session.commit()
    return result.rowcount or 0


async def request_cancel(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError("任务不存在")
    job.cancel_requested = True
    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.CANCELED
        job.stage = "已取消"
        job.finished_at = utcnow()
    await session.commit()
    return job


async def mark_progress(
    session: AsyncSession,
    job_id: str,
    *,
    progress: int,
    stage: str,
) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(progress=max(0, min(100, progress)), stage=stage)
    )
    await session.commit()


async def _process_one(session: AsyncSession, job: Job) -> None:
    job_id = job.id
    job_kind = job.kind
    if job_kind not in _handlers:
        from app.services import handlers  # noqa: F401
    handler = _handlers.get(job_kind)
    if handler is None:
        raise RuntimeError(f"未注册任务类型: {job_kind}")
    try:
        fresh = await session.get(Job, job_id)
        if fresh and fresh.cancel_requested:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=JobStatus.CANCELED,
                    stage="已取消",
                    lease_owner=None,
                    lease_until=None,
                    finished_at=utcnow(),
                )
            )
            await session.commit()
            return
        result = await handler(session, job) or {}
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                progress=100,
                stage="完成",
                result=result,
                error=None,
                lease_owner=None,
                lease_until=None,
                finished_at=utcnow(),
            )
        )
        await session.commit()
    except Exception as exc:
        logger.exception("job failed: %s", job_id)
        await session.rollback()
        fresh = await session.get(Job, job_id)
        if fresh is None:
            return
        retry = fresh.attempts < fresh.max_attempts
        if fresh.kind == "analyze_project" and not retry:
            run = await session.get(AnalysisRun, fresh.payload.get("run_id", ""))
            if run is not None:
                run.status = AnalysisStatus.FAILED
                run.progress = 100
                run.stage = "analysis_failed"
                run.error = f"{type(exc).__name__}: {exc}"[:4000]
                run.finished_at = utcnow()
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.QUEUED if retry else JobStatus.FAILED,
                stage="等待重试" if retry else "失败",
                error=f"{type(exc).__name__}: {exc}"[:4000],
                lease_owner=None,
                lease_until=None,
                available_at=utcnow() + timedelta(seconds=2**fresh.attempts),
                finished_at=None if retry else utcnow(),
            )
        )
        await session.commit()


async def worker_loop(stop_event: asyncio.Event, poll_seconds: float, lease_seconds: int) -> None:
    worker_id = f"{socket.gethostname()}:{id(stop_event)}"
    logger.info("worker started: %s", worker_id)
    while not stop_event.is_set():
        session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with session_factory() as session:
            await recover_expired_jobs(session)
            job = await claim_job(session, worker_id, lease_seconds)
            if job is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
                except TimeoutError:
                    pass
                except asyncio.CancelledError:
                    stop_event.set()
                    return
                continue
            await _process_one(session, job)
    logger.info("worker stopped: %s", worker_id)
