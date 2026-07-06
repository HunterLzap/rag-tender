"""匹配任务触发前清理旧结果的回归测试。"""

import asyncio
import os
import platform
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

platform._wmi = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.services import match_service


class MatchTriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(self.db_path)
        asyncio.run(init_db())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO tenders
                   (id, filename, original_path, pdf_path, title, status, total_pages, created_at)
                   VALUES (1, 'sample.pdf', 'sample.pdf', 'sample.pdf',
                           'sample', 'completed', 1, '2026-06-24')"""
            )
            conn.execute(
                """INSERT INTO tender_requirements
                   (id, tender_id, category, title, content, created_at)
                   VALUES (1, 1, 'qualification', '营业执照', '须提供营业执照', '2026-06-24')"""
            )
            conn.execute(
                """INSERT INTO match_results
                   (tender_id, requirement_id, status, created_at)
                   VALUES (1, 1, 'matched', '2026-06-24')"""
            )
            conn.commit()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_clear_match_results_removes_previous_run(self) -> None:
        deleted = asyncio.run(match_service.clear_match_results(1))

        self.assertEqual(1, deleted)
        self.assertEqual([], asyncio.run(match_service.get_match_results(1)))


if __name__ == "__main__":
    unittest.main()
