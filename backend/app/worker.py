import asyncio
import logging
import signal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import create_schema, get_engine, utcnow
from app.models import Job, JobStatus
from app.services import handlers  # noqa: F401
from app.services.jobs import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def fail_running_jobs() -> None:
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        await session.execute(
            update(Job)
            .where(Job.status == JobStatus.RUNNING)
            .values(
                status=JobStatus.QUEUED,
                stage="worker 启动后恢复任务",
                lease_owner=None,
                lease_until=None,
                finished_at=None,
                updated_at=utcnow(),
            )
        )
        await session.commit()


async def main() -> None:
    settings = get_settings()
    if settings.auto_create_schema:
        await create_schema()
    await fail_running_jobs()
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
