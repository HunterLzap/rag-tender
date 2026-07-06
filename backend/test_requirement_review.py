"""标书要求核对能力回归测试。"""

import asyncio
import os
import platform
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

platform._wmi = None  # 避免当前 Windows 环境 WMI 查询阻塞第三方依赖导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.schemas.tender import TenderRequirementUpdate
from app.services import tender_service


class RequirementReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.pdf_path = Path(self.temp_dir.name) / "sample.pdf"
        self.pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(self.db_path)
        asyncio.run(init_db())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO tenders
                   (id, filename, original_path, pdf_path, title, status, total_pages, created_at)
                   VALUES (1, 'sample.pdf', ?, ?, 'sample', 'completed', 20, '2026-06-24')""",
                (str(self.pdf_path), str(self.pdf_path)),
            )
            conn.execute(
                """INSERT INTO tender_requirements
                   (id, tender_id, category, title, content, is_hard, raw_text,
                    page_number, created_at)
                   VALUES
                   (1, 1, 'qualification', '营业执照', '须提供营业执照', 1, '原文A', 3, '2026-06-24'),
                   (2, 1, 'financial', '财务报告', '须提供财务报告', 0, '原文B', NULL, '2026-06-24')"""
            )
            conn.commit()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_update_and_batch_confirm_requirements(self) -> None:
        updated = asyncio.run(
            tender_service.update_requirement(
                1,
                1,
                TenderRequirementUpdate(title="有效营业执照", page_number=5),
            )
        )
        self.assertEqual("有效营业执照", updated.title)
        self.assertEqual(5, updated.page_number)

        count = asyncio.run(
            tender_service.batch_update_requirement_status(1, [1, 2], "confirmed")
        )
        self.assertEqual(2, count)

        requirements = asyncio.run(tender_service.get_tender_requirements(1))
        self.assertEqual(["confirmed", "confirmed"], [r.review_status for r in requirements])

    def test_delete_requirement_and_resolve_pdf(self) -> None:
        created = asyncio.run(
            tender_service.create_requirement(
                1,
                TenderRequirementUpdate(
                    category="personnel",
                    title="项目经理",
                    content="须配备项目经理",
                    page_number=8,
                ),
            )
        )
        self.assertEqual("项目经理", created.title)

        deleted = asyncio.run(tender_service.delete_requirement(1, 2))
        self.assertTrue(deleted)
        remaining = asyncio.run(tender_service.get_tender_requirements(1))
        self.assertEqual(2, len(remaining))

        resolved = asyncio.run(tender_service.get_tender_pdf_path(1))
        self.assertEqual(str(self.pdf_path), resolved)


if __name__ == "__main__":
    unittest.main()
