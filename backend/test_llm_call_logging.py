"""LLM 调用记录测试。"""

import asyncio
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.models.config_model import ApiConfig
from app.utils import llm_helpers


class LlmCallLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(self.db_path)
        asyncio.run(init_db())

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_llm_call_log_records_model_duration_and_never_plain_api_key(self) -> None:
        async def fake_request(**kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

        original = llm_helpers._openai_chat_request
        llm_helpers._openai_chat_request = fake_request
        try:
            func = llm_helpers.build_llm_func(
                ApiConfig(
                    config_type="llm",
                    provider="test",
                    base_url="https://example.test/v1",
                    api_key="unit-test-secret-plain-key",
                    model_name="demo-model",
                )
            )
            result = asyncio.run(func("hello", task_type="unit_test"))
        finally:
            llm_helpers._openai_chat_request = original

        self.assertEqual("ok", result)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT task_type, config_type, model_name, success, duration_ms, error_message, api_key_fingerprint FROM llm_call_logs"
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual("unit_test", row[0])
        self.assertEqual("llm", row[1])
        self.assertEqual("demo-model", row[2])
        self.assertEqual(1, row[3])
        self.assertGreaterEqual(row[4], 0)
        self.assertIsNone(row[5])
        expected_fingerprint = hashlib.sha256(
            "unit-test-secret-plain-key".encode("utf-8")
        ).hexdigest()[:12]
        self.assertEqual(expected_fingerprint, row[6])
        self.assertNotIn("unit-test-secret-plain-key", row[6] or "")
        self.assertNotIn("len:", row[6] or "")
        self.assertNotIn("suffix:", row[6] or "")
        self.assertNotIn("key", row[6] or "")


if __name__ == "__main__":
    unittest.main()
