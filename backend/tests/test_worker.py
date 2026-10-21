from datetime import timedelta

from app.db import utcnow
from app.models import AnalysisRun, AnalysisStatus, Job, JobStatus
from app.services.jobs import fail_exhausted_jobs
from app.worker import fail_running_jobs


async def test_worker_startup_does_not_revive_exhausted_jobs(session):
    run = AnalysisRun(project_id="missing", status=AnalysisStatus.RUNNING)
    session.add(run)
    await session.flush()
    job = Job(
        kind="analyze_project",
        payload={"run_id": run.id},
        status=JobStatus.RUNNING,
        attempts=1,
        max_attempts=1,
        error="previous failure",
    )
    session.add(job)
    await session.commit()

    await fail_running_jobs(session)
    await session.refresh(job)
    await session.refresh(run)

    assert job.status == JobStatus.FAILED
    assert job.finished_at is not None
    assert run.status == AnalysisStatus.FAILED
    assert run.error == "previous failure"


async def test_worker_startup_recovers_retryable_jobs(session):
    job = Job(
        kind="parse_document",
        payload={},
        status=JobStatus.RUNNING,
        attempts=1,
        max_attempts=3,
    )
    session.add(job)
    await session.commit()

    await fail_running_jobs(session)
    await session.refresh(job)

    assert job.status == JobStatus.QUEUED
    assert job.lease_owner is None
    assert job.lease_until is None


async def test_expired_analysis_fails_without_repeating_model_work(session):
    run = AnalysisRun(project_id="missing", status=AnalysisStatus.RUNNING)
    session.add(run)
    await session.flush()
    job = Job(
        kind="analyze_project",
        payload={"run_id": run.id},
        status=JobStatus.RUNNING,
        attempts=1,
        max_attempts=1,
        lease_until=utcnow() - timedelta(seconds=1),
    )
    session.add(job)
    await session.commit()

    assert await fail_exhausted_jobs(session) == 1
    await session.refresh(job)
    await session.refresh(run)
    assert job.status == JobStatus.FAILED
    assert run.status == AnalysisStatus.FAILED
