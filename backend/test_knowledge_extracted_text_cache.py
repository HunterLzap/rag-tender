"""知识库文件 OCR/文本提取缓存测试。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.services import knowledge_service


def test_cached_extracted_text_is_reused_without_ocr() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "text_cache.db")
        asyncio.run(_assert_cached_text_reused(tmp_dir.name))
    finally:
        tmp_dir.cleanup()


async def _assert_cached_text_reused(tmp_dir: str) -> None:
    await init_db()
    file_path = str(Path(tmp_dir) / "cached.pdf")
    Path(file_path).write_bytes(b"%PDF-1.4 fake")

    db = await database.get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO knowledge_files
               (filename, file_path, file_type, category, status, upload_time, created_at,
                extracted_text, extracted_at)
               VALUES (?, ?, 'pdf', 'enterprise', 'completed', '2026-06-29 10:00:00',
                       '2026-06-29 10:00:00', ?, '2026-06-29 10:01:00')""",
            (
                "cached.pdf",
                file_path,
                "营业执照\n统一社会信用代码：91310000MA1TEST000\n名称：上海某某科技有限公司",
            ),
        )
        file_id = cursor.lastrowid
        await db.commit()
    finally:
        await db.close()

    original_extract = knowledge_service._extract_pdf_text_with_ocr_fallback
    try:
        async def fail_if_called(_pdf_path: str) -> str:
            raise AssertionError("OCR/text extraction should not run when cached text exists")

        knowledge_service._extract_pdf_text_with_ocr_fallback = fail_if_called
        text = await knowledge_service._get_or_extract_file_text(file_id, file_path, "pdf")
    finally:
        knowledge_service._extract_pdf_text_with_ocr_fallback = original_extract

    assert "统一社会信用代码" in text


if __name__ == "__main__":
    test_cached_extracted_text_is_reused_without_ocr()
    print("knowledge extracted text cache tests passed")
