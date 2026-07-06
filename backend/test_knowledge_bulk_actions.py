"""知识库资质批量操作测试。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.services import knowledge_service


def test_bulk_update_category_updates_qualifications_and_source_files() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
      database.DB_PATH = str(Path(tmp_dir.name) / "bulk_update.db")
      asyncio.run(_assert_bulk_update_category(tmp_dir.name))
    finally:
      tmp_dir.cleanup()


def test_bulk_delete_removes_source_files_related_qualifications_and_manual_records() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
      database.DB_PATH = str(Path(tmp_dir.name) / "bulk_delete.db")
      asyncio.run(_assert_bulk_delete(tmp_dir.name))
    finally:
      tmp_dir.cleanup()


def test_get_incomplete_qualification_file_ids_filters_by_category() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
      database.DB_PATH = str(Path(tmp_dir.name) / "incomplete.db")
      asyncio.run(_assert_incomplete_file_ids(tmp_dir.name))
    finally:
      tmp_dir.cleanup()


async def _insert_file_and_qualification(
    file_path: str,
    category: str,
    name: str,
) -> tuple[int, int]:
    db = await database.get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO knowledge_files
               (filename, file_path, file_type, category, status, upload_time, created_at)
               VALUES (?, ?, 'pdf', ?, 'completed', '2026-06-26 10:00:00', '2026-06-26 10:00:00')""",
            (Path(file_path).name, file_path, category),
        )
        file_id = cursor.lastrowid
        cursor = await db.execute(
            """INSERT INTO qualifications
               (file_id, name, number, category, status, created_at)
               VALUES (?, ?, ?, ?, 'valid', '2026-06-26 10:00:00')""",
            (file_id, name, f"NO-{name}", category),
        )
        qual_id = cursor.lastrowid
        await db.commit()
        return file_id, qual_id
    finally:
        await db.close()


async def _assert_bulk_update_category(tmp_dir: str) -> None:
    await init_db()
    file_path = str(Path(tmp_dir) / "enterprise-cert.pdf")
    Path(file_path).write_text("fake pdf", encoding="utf-8")
    file_id, qual_id = await _insert_file_and_qualification(
        file_path=file_path,
        category="personnel",
        name="营业执照",
    )

    result = await knowledge_service.bulk_update_qualification_category(
        [qual_id],
        "enterprise",
    )

    assert result == {
        "updated_qualification_count": 1,
        "updated_file_count": 1,
        "missing_qualification_ids": [],
    }

    db = await database.get_db()
    try:
        qual_row = await (
            await db.execute("SELECT category FROM qualifications WHERE id = ?", (qual_id,))
        ).fetchone()
        file_row = await (
            await db.execute("SELECT category FROM knowledge_files WHERE id = ?", (file_id,))
        ).fetchone()
    finally:
        await db.close()

    assert qual_row["category"] == "enterprise"
    assert file_row["category"] == "enterprise"


async def _assert_bulk_delete(tmp_dir: str) -> None:
    await init_db()
    file_path = str(Path(tmp_dir) / "wrong-category.pdf")
    Path(file_path).write_text("fake pdf", encoding="utf-8")
    file_id, qual_id = await _insert_file_and_qualification(
        file_path=file_path,
        category="personnel",
        name="ISO证书",
    )

    db = await database.get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO qualifications
               (file_id, name, number, category, status, created_at)
               VALUES (?, '同文件第二条资质', 'NO-2', 'personnel', 'valid', '2026-06-26 10:00:00')""",
            (file_id,),
        )
        sibling_qual_id = cursor.lastrowid
        cursor = await db.execute(
            """INSERT INTO qualifications
               (file_id, name, number, category, status, created_at)
               VALUES (NULL, '手动资质', 'MANUAL-1', 'personnel', 'valid', '2026-06-26 10:00:00')""",
        )
        manual_qual_id = cursor.lastrowid
        await db.commit()
    finally:
        await db.close()

    result = await knowledge_service.bulk_delete_qualifications_by_source(
        [qual_id, manual_qual_id],
    )

    assert result == {
        "deleted_file_count": 1,
        "deleted_manual_qualification_count": 1,
        "deleted_related_qualification_count": 2,
        "missing_qualification_ids": [],
    }
    assert not Path(file_path).exists()

    db = await database.get_db()
    try:
        file_row = await (
            await db.execute("SELECT id FROM knowledge_files WHERE id = ?", (file_id,))
        ).fetchone()
        selected_row = await (
            await db.execute("SELECT id FROM qualifications WHERE id = ?", (qual_id,))
        ).fetchone()
        sibling_row = await (
            await db.execute("SELECT id FROM qualifications WHERE id = ?", (sibling_qual_id,))
        ).fetchone()
        manual_row = await (
            await db.execute("SELECT id FROM qualifications WHERE id = ?", (manual_qual_id,))
        ).fetchone()
    finally:
        await db.close()

    assert file_row is None
    assert selected_row is None
    assert sibling_row is None
    assert manual_row is None


async def _assert_incomplete_file_ids(tmp_dir: str) -> None:
    await init_db()
    personnel_path = str(Path(tmp_dir) / "personnel-id.pdf")
    enterprise_path = str(Path(tmp_dir) / "enterprise-cert.pdf")
    Path(personnel_path).write_text("fake pdf", encoding="utf-8")
    Path(enterprise_path).write_text("fake pdf", encoding="utf-8")
    personnel_file_id, personnel_qual_id = await _insert_file_and_qualification(
        file_path=personnel_path,
        category="personnel",
        name="身份证明",
    )
    enterprise_file_id, enterprise_qual_id = await _insert_file_and_qualification(
        file_path=enterprise_path,
        category="enterprise",
        name="营业执照",
    )

    db = await database.get_db()
    try:
        await db.execute(
            "UPDATE qualifications SET status = 'needs_completion', scope = '待人工补全：扫描件' WHERE id = ?",
            (personnel_qual_id,),
        )
        await db.execute(
            "UPDATE qualifications SET status = 'needs_completion', scope = '待人工补全：扫描件' WHERE id = ?",
            (enterprise_qual_id,),
        )
        await db.commit()
    finally:
        await db.close()

    assert await knowledge_service.get_incomplete_qualification_file_ids("personnel") == [
        personnel_file_id
    ]
    assert await knowledge_service.get_incomplete_qualification_file_ids("enterprise") == [
        enterprise_file_id
    ]


if __name__ == "__main__":
    test_bulk_update_category_updates_qualifications_and_source_files()
    test_bulk_delete_removes_source_files_related_qualifications_and_manual_records()
    test_get_incomplete_qualification_file_ids_filters_by_category()
    print("knowledge bulk action tests passed")
