"""投标待办清单红线规则测试。"""

import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.services import rule_library_service, submission_checklist_service


class ChecklistRedFlagTests(unittest.TestCase):
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
                   VALUES (1, 'sample.pdf', 'sample.pdf', 'sample', 'completed', '2026-07-01')"""
            )
            conn.execute(
                """INSERT INTO tender_requirements
                   (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
                   VALUES
                   (1, 1, 'submission', 'submission', '投标保证金',
                    '投标人须在投标截止时间前缴纳投标保证金，逾期视为无效投标。', 1, '原文A', '2026-07-01'),
                   (2, 1, 'submission', 'submission', '签章密封',
                    '投标文件应按要求签字盖章并密封提交。', 1, '原文B', '2026-07-01'),
                   (3, 1, 'submission', 'submission', '普通附件',
                    '须提交售后服务承诺函。', 0, '原文C', '2026-07-01'),
                   (4, 1, 'submission', 'submission', '授权委托书',
                    '投标文件须提供法定代表人授权委托书及被授权人身份证。', 1, '原文D', '2026-07-01'),
                   (5, 1, 'submission', 'submission', '投标有效期',
                    '投标有效期不少于90日，不满足将按无效投标处理。', 1, '原文E', '2026-07-01'),
                   (6, 1, 'submission', 'submission', '报价上限',
                    '投标报价不得超过最高限价120万元，否则投标无效。', 1, '原文F', '2026-07-01'),
                   (7, 1, 'submission', 'submission', '暗标编制',
                    '技术暗标不得出现投标人名称、联系人、电话、地址等可识别信息。', 1, '原文G', '2026-07-01')"""
            )
            conn.commit()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_init_marks_submission_red_flags_without_duplicates(self) -> None:
        first = asyncio.run(submission_checklist_service.get_all(1))
        second = asyncio.run(submission_checklist_service.get_all(1))

        self.assertEqual(7, len(first))
        self.assertEqual(7, len(second))

        by_name = {item.item_name: item for item in first}
        self.assertIn("【红线】", by_name["投标保证金"].remark or "")
        self.assertIn("保证金", by_name["投标保证金"].remark or "")
        self.assertIn("【红线】", by_name["签章密封"].remark or "")
        self.assertIn("签章/密封", by_name["签章密封"].remark or "")
        self.assertNotIn("【红线】", by_name["普通附件"].remark or "")
        self.assertIn("授权书", by_name["授权委托书"].remark or "")
        self.assertIn("投标有效期", by_name["投标有效期"].remark or "")
        self.assertIn("报价上限", by_name["报价上限"].remark or "")
        self.assertIn("暗标", by_name["暗标编制"].remark or "")

    def test_get_all_backfills_red_flags_for_existing_checklist(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO submission_checklist
                   (tender_id, requirement_id, item_name, description, status, remark, created_at, updated_at)
                   VALUES (1, 1, '投标保证金',
                           '投标人须在投标截止时间前缴纳投标保证金，逾期视为无效投标。',
                           'not_started', NULL, '2026-07-01', '2026-07-01')"""
            )
            conn.commit()

        items = asyncio.run(submission_checklist_service.get_all(1))

        self.assertEqual(1, len(items))
        self.assertIn("【红线】", items[0].remark or "")
        self.assertIn("保证金", items[0].remark or "")

    def test_format_self_defined_is_not_red_flag_and_stale_system_remark_is_removed(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """DELETE FROM submission_checklist WHERE tender_id = 1"""
            )
            conn.execute(
                """INSERT INTO submission_checklist
                   (tender_id, requirement_id, item_name, description, status, remark, created_at, updated_at)
                   VALUES (1, 3, '供货安装方案',
                           '投标人须提交供货安装方案，格式自定',
                           'not_started',
                           '人工备注；【红线】格式/份数：正副本、格式、装订或页码不符合要求可能影响响应有效性',
                           '2026-07-01', '2026-07-01')"""
            )
            conn.commit()

        items = asyncio.run(submission_checklist_service.get_all(1))

        self.assertEqual(1, len(items))
        self.assertEqual("人工备注", items[0].remark)

    def test_disabled_red_flag_rule_does_not_mark_checklist_item(self) -> None:
        asyncio.run(
            rule_library_service.update_rule_enabled(
                "submission.red_flag.deposit",
                False,
            )
        )

        items = asyncio.run(submission_checklist_service.get_all(1))

        by_name = {item.item_name: item for item in items}
        self.assertNotIn("保证金：", by_name["投标保证金"].remark or "")
        self.assertIn("截止时间：", by_name["投标保证金"].remark or "")
        self.assertIn("【红线】", by_name["签章密封"].remark or "")


if __name__ == "__main__":
    unittest.main()
