"""轻量检查器接口和检查报告导出测试。"""

import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from app import database
from app.database import init_db
from app.main import app
from app.services.checker_service import CheckContext, run_checkers


class CheckerAndReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(self.db_path)
        asyncio.run(init_db())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO tenders
                   (id, filename, original_path, title, status, created_at)
                   VALUES (1, 'demo.pdf', 'demo.pdf', '演示项目', 'completed', '2026-07-01')"""
            )
            conn.execute(
                """INSERT INTO tender_requirements
                   (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
                   VALUES (1, 1, 'qualification', 'capability', '资质证书',
                           '须提供有效资质证书。', 1, '原文A', '2026-07-01'),
                          (2, 1, 'submission', 'submission', '投标有效期',
                           '投标有效期不少于90日。', 1, '原文B', '2026-07-01')"""
            )
            conn.execute(
                """INSERT INTO match_results
                   (id, tender_id, requirement_id, status, reason, mismatch_detail,
                    expected_qualification, in_knowledge_base, similarity_score, evidence_items, created_at)
                   VALUES (1, 1, 1, 'needs_review', '缺少有效期证据', '未找到证书有效期',
                           '有效资质证书', 1, 0.72,
                           '[{"check_key":"expiry","label":"有效期","status":"unknown","critical":true}]',
                           '2026-07-01')"""
            )
            conn.execute(
                """INSERT INTO submission_checklist
                   (id, tender_id, requirement_id, item_name, description, status, remark, created_at, updated_at)
                   VALUES (1, 1, 2, '投标有效期', '投标有效期不少于90日。',
                           'not_started', '【红线】投标有效期：有效期短于要求可能导致投标无效',
                           '2026-07-01', '2026-07-01')"""
            )
            conn.commit()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_run_checkers_returns_uniform_result_shape(self) -> None:
        result = asyncio.run(run_checkers(CheckContext(tender_id=1), checker_ids=["submission.red_flags"]))

        self.assertEqual(1, len(result))
        self.assertEqual("submission.red_flags", result[0].checker_id)
        self.assertEqual("needs_review", result[0].status)
        self.assertEqual("high", result[0].risk_level)
        self.assertGreaterEqual(len(result[0].evidence), 1)

    def test_run_checkers_returns_low_risk_when_all_red_flags_done(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE submission_checklist SET status = 'done' WHERE tender_id = 1")
            conn.commit()

        result = asyncio.run(run_checkers(CheckContext(tender_id=1), checker_ids=["submission.red_flags"]))

        self.assertEqual("pass", result[0].status)
        self.assertEqual("low", result[0].risk_level)
        self.assertEqual("pass", result[0].evidence[0].status)
        self.assertEqual([], result[0].suggested_actions)

    def test_run_checkers_returns_low_risk_when_no_red_flags(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM submission_checklist WHERE tender_id = 1")
            conn.execute(
                """INSERT INTO submission_checklist
                   (id, tender_id, requirement_id, item_name, description, status, remark, created_at, updated_at)
                   VALUES (2, 1, NULL, '普通资料', '提交售后服务承诺函。',
                           'not_started', NULL, '2026-07-01', '2026-07-01')"""
            )
            conn.commit()

        result = asyncio.run(run_checkers(CheckContext(tender_id=1), checker_ids=["submission.red_flags"]))

        self.assertEqual("pass", result[0].status)
        self.assertEqual("low", result[0].risk_level)
        self.assertEqual([], result[0].evidence)
        self.assertEqual([], result[0].suggested_actions)

    def test_check_report_export_contains_matches_and_red_flags(self) -> None:
        client = TestClient(app)

        resp = client.get("/api/v1/tenders/1/check-report/export")

        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(0, body["code"])
        self.assertEqual("演示项目_check_report.md", body["data"]["filename"])
        self.assertIn("资质匹配总览", body["data"]["content"])
        self.assertIn("缺少有效期证据", body["data"]["content"])
        self.assertIn("投标有效期", body["data"]["content"])


if __name__ == "__main__":
    unittest.main()
