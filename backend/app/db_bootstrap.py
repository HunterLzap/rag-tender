"""Bring local v2 databases to the latest Alembic revision.

Early v2 development databases were created with create_all and have no Alembic
version table. They are baselined only after confirming the v2 domain tables
exist; this intentionally does not migrate the old RAG schema.
"""

import asyncio
import sqlite3
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.config import get_settings

V2_TABLES = {"projects", "documents", "analysis_runs", "fill_suggestions"}
BASELINE_REVISION = "fcb21467dc21"
KNOWN_REVISIONS = {BASELINE_REVISION, "a19b2f0e71d4"}


async def _table_names() -> set[str]:
    engine = create_async_engine(get_settings().resolved_database_url)
    try:
        async with engine.connect() as connection:
            return set(
                await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            )
    finally:
        await engine.dispose()


def _has_alembic_version(database_url: str) -> bool:
    if not database_url.startswith("sqlite"):
        return True
    path = database_url.split("///", 1)[-1].split("?", 1)[0]
    if path == ":memory:" or not Path(path).exists():
        return False
    with sqlite3.connect(path, timeout=30) as connection:
        return bool(
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            ).fetchone()
        )


def bootstrap() -> None:
    settings = get_settings()
    tables = asyncio.run(_table_names())
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    if settings.resolved_database_url.startswith("sqlite") and V2_TABLES.issubset(tables):
        path = settings.resolved_database_url.split("///", 1)[-1].split("?", 1)[0]
        with sqlite3.connect(path, timeout=30) as connection:
            current = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() if _has_alembic_version(settings.resolved_database_url) else None
            if current is None:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(32) NOT NULL)"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO alembic_version (version_num) VALUES (?)",
                    (BASELINE_REVISION,),
                )
            elif current[0] not in KNOWN_REVISIONS:
                raise RuntimeError(
                    f"unexpected alembic revision {current[0]}; "
                    f"expected one of {sorted(KNOWN_REVISIONS)}"
                )
    command.upgrade(config, "head")


if __name__ == "__main__":
    bootstrap()
