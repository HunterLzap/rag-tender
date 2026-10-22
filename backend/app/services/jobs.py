import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_engine, utcnow
from app.models import AnalysisRun, AnalysisStatus, Document, Job, JobStatus

logger = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, Job], Awaitable[dict[str, Any] | None]]
_handlers: dict[str, Handler] = {}


class JobCanceled(RuntimeError):
    pass


async def check_canceled(session: AsyncSession, job_id: str | None) -> None:
    if (
        job_id
        and (
            await session.execute(select(Job.cancel_requested).where(Job.id == job_id))
        ).scalar_one_or_none()
    ):
        raise JobCanceled("任务已取消")


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
        # Model-backed work must not be repeated automatically after a partial run.
        max_attempts=3 if kind == "parse_document" else 1,
    )
    if kind in {"parse_document", "process_document"}:
        document = await session.get(
            __import__("app.models", fromlist=["Document"]).Document, payload["document_id"]
        )
        if document is not None:
            job.payload = {
                **job.payload,
                "project_id": document.project_id,
                "organization_id": document.organization_id,
            }
    elif kind == "analyze_project":
        run = await session.get(
            __import__("app.models", fromlist=["AnalysisRun"]).AnalysisRun,
            payload["run_id"],
        )
        if run is not None:
            job.payload = {**job.payload, "project_id": run.project_id}
    elif kind == "draft_fill_plan":
        from app.models import FillPlan

        plan = await session.get(FillPlan, payload["plan_id"])
        run = await session.get(AnalysisRun, plan.run_id)
        job.payload = {**job.payload, "project_id": run.project_id, "run_id": run.id}
    session.add(job)
    await session.flush()
    return job


async def claim_job(session: AsyncSession, worker_id: str, lease_seconds: int) -> Job | None:
    from app.config import get_settings

    now = utcnow()
    allowed = (
        []
        if get_settings().live_model_calls
        else [
            Job.kind.notin_(["process_document", "analyze_project", "draft_fill_plan"]),
        ]
    )
    candidate = (
        await session.execute(
            select(Job.id)
            .where(Job.status == JobStatus.QUEUED, Job.available_at <= now, *allowed)
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
    canceled = (await session.execute(select(Job).where(
        Job.status == JobStatus.RUNNING, Job.cancel_requested.is_(True),
        Job.lease_until.is_not(None), Job.lease_until < now,
    ))).scalars().all()
    for job in canceled:
        await finish_canceled_job(session, job)
    result = await session.execute(
        update(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.lease_until.is_not(None),
            Job.lease_until < now,
            Job.attempts < Job.max_attempts,
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


async def fail_exhausted_jobs(session: AsyncSession) -> int:
    now = utcnow()
    result = await session.execute(
        update(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.lease_until.is_not(None),
            Job.lease_until < now,
            Job.attempts >= Job.max_attempts,
            Job.cancel_requested.is_(False),
        )
        .values(
            status=JobStatus.FAILED,
            stage="失败：超过最大重试次数",
            lease_owner=None,
            lease_until=None,
            finished_at=now,
        )
        .returning(Job.kind, Job.payload)
    )
    failed = result.all()
    for kind, payload in failed:
        if kind == "analyze_project":
            await session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == payload.get("run_id"))
                .values(
                    status=AnalysisStatus.FAILED,
                    stage="analysis_failed",
                    error="任务超时，未自动重复模型调用",
                    finished_at=now,
                )
            )
        elif kind == "parse_document":
            document = await session.get(Document, payload.get("document_id"))
            if document:
                document.metadata_json = {
                    **(document.metadata_json or {}),
                    "parse_status": "failed",
                    "parse_error": "解析任务超时，请手动重试",
                }
        elif kind == "process_document":
            document = await session.get(Document, payload.get("document_id"))
            if document:
                document.metadata_json = {
                    **document.metadata_json,
                    "ai_status": "failed",
                    "ai_error": "AI 入库任务超时，请检查模型设置后重试",
                }
        elif kind == "draft_fill_plan":
            from app.models import FillPlan

            plan = await session.get(FillPlan, payload.get("plan_id"))
            if plan:
                plan.status = "failed"
    await session.commit()
    return len(failed)


async def finish_canceled_job(session: AsyncSession, job: Job) -> None:
    job.status = JobStatus.CANCELED
    job.stage = "已取消"
    job.finished_at = utcnow()
    if job.kind == "analyze_project":
        run = await session.get(AnalysisRun, job.payload.get("run_id"))
        if run:
            run.status = AnalysisStatus.FAILED
            run.stage = "analysis_canceled"
            run.error = "任务已取消"
            run.finished_at = utcnow()
    elif job.kind == "parse_document":
        document = await session.get(Document, job.payload.get("document_id"))
        if document:
            document.metadata_json = {
                **(document.metadata_json or {}),
                "parse_status": "canceled",
                "parse_error": "解析任务已取消",
            }
    elif job.kind == "process_document":
        document = await session.get(Document, job.payload.get("document_id"))
        if document:
            document.metadata_json = {
                **document.metadata_json,
                "ai_status": "canceled",
                "ai_error": "任务已取消",
            }
    elif job.kind == "draft_fill_plan":
        from app.models import FillPlan

        plan = await session.get(FillPlan, job.payload.get("plan_id"))
        if plan:
            plan.status = "canceled"
    job.lease_owner = None
    job.lease_until = None


async def request_cancel(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError("任务不存在")
    job.cancel_requested = True
    if job.status == JobStatus.QUEUED:
        await finish_canceled_job(session, job)
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
        update(Job).where(Job.id == job_id).values(progress=max(0, min(100, progress)), stage=stage)
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
        await check_canceled(session, job_id)
        result = await handler(session, job) or {}
        await check_canceled(session, job_id)
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
        canceled = isinstance(exc, JobCanceled) or fresh.cancel_requested
        retry = not canceled and fresh.attempts < fresh.max_attempts
        if fresh.kind == "analyze_project" and not retry:
            run = await session.get(AnalysisRun, fresh.payload.get("run_id", ""))
            if run is not None:
                run.status = AnalysisStatus.FAILED
                run.progress = 100
                run.stage = "analysis_canceled" if canceled else "analysis_failed"
                run.error = f"{type(exc).__name__}: {exc}"[:4000]
                run.finished_at = utcnow()
        elif fresh.kind == "parse_document":
            document = await session.get(Document, fresh.payload.get("document_id"))
            if document:
                document.metadata_json = {
                    **(document.metadata_json or {}),
                    "parse_status": "canceled" if canceled else "queued" if retry else "failed",
                    "parse_error": f"{type(exc).__name__}: {exc}"[:2000],
                }
        elif fresh.kind == "process_document":
            document = await session.get(Document, fresh.payload.get("document_id"))
            if document:
                document.metadata_json = {
                    **document.metadata_json,
                    "ai_status": "canceled" if canceled else "failed",
                    "ai_error": f"{type(exc).__name__}: {exc}"[:2000],
                }
        elif fresh.kind == "draft_fill_plan":
            from app.models import FillPlan

            plan = await session.get(FillPlan, fresh.payload.get("plan_id"))
            if plan:
                plan.status = "canceled" if canceled else "failed"
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=(
                    JobStatus.CANCELED
                    if canceled
                    else JobStatus.QUEUED
                    if retry
                    else JobStatus.FAILED
                ),
                stage="已取消" if canceled else "等待重试" if retry else "失败",
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
            await fail_exhausted_jobs(session)
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
            if job.kind == "analyze_project" and job.status == JobStatus.COMPLETED:
                from app.models import Project
                from app.services.pipeline import schedule_analysis

                project = await session.get(Project, job.payload.get("project_id"))
                if project and project.auto_analyze and project.status == "active":
                    await schedule_analysis(session, project, automatic=True)
                    await session.commit()
    logger.info("worker stopped: %s", worker_id)
