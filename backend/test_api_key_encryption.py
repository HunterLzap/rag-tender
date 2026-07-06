"""API Key encryption behavior tests.

These tests use an isolated SQLite database and a test Fernet key. They must
never read or write the real user database.
"""

import asyncio
import atexit
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from app import database

_TEST_DB_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
atexit.register(_TEST_DB_DIR.cleanup)
database.DB_PATH = str(Path(_TEST_DB_DIR.name) / "test_api_key_encryption.db")

os.environ["RAG_TENDER_SECRET_KEY"] = (
    "cD6h7vUv8yaCEvCwkO-9xb41E6cVD_0Vtcfs7AFzTZ0="
)

from app.database import init_db
from app.main import app
from app.services import config_service


def _reset_db() -> None:
    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM api_configs")
        conn.commit()


def _raw_api_key(config_type: str) -> str:
    with sqlite3.connect(database.DB_PATH) as conn:
        row = conn.execute(
            "SELECT api_key FROM api_configs WHERE config_type = ? LIMIT 1",
            (config_type,),
        ).fetchone()
        assert row is not None
        return row[0]


def test_saved_api_key_is_encrypted_but_returned_masked() -> None:
    _reset_db()

    saved = asyncio.run(
        config_service.save_config(
            config_type="llm",
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key="unit-test-key-1234567890abcdef",
            model_name="deepseek-chat",
        )
    )

    raw_key = _raw_api_key("llm")
    assert saved["api_key"] == "****cdef"
    assert raw_key.startswith("enc:")
    assert raw_key != "unit-test-key-1234567890abcdef"
    assert "unit-test-key" not in raw_key

    configs = asyncio.run(config_service.get_all_configs())
    assert configs[0]["api_key"] == "****cdef"


def test_masked_update_preserves_encrypted_key() -> None:
    _reset_db()
    asyncio.run(
        config_service.save_config(
            config_type="embedding",
            provider="qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="unit-original-abcdef123456",
            model_name="text-embedding-v3",
        )
    )
    encrypted_before = _raw_api_key("embedding")

    updated = asyncio.run(
        config_service.save_config(
            config_type="embedding",
            provider="qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="****3456",
            model_name="text-embedding-v3-new",
        )
    )

    assert updated["api_key"] == "****3456"
    assert _raw_api_key("embedding") == encrypted_before


def test_legacy_plaintext_keys_are_migrated_on_init() -> None:
    _reset_db()
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO api_configs
               (config_type, provider, base_url, api_key, model_name, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, '2026-01-01', '2026-01-01')""",
            (
                "vision",
                "qwen",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "unit-legacy-vision-key",
                "qwen-vl-max",
            ),
        )
        conn.commit()

    asyncio.run(init_db())

    raw_key = _raw_api_key("vision")
    assert raw_key.startswith("enc:")
    assert raw_key != "unit-legacy-vision-key"


def test_config_debug_db_endpoint_is_not_available() -> None:
    _reset_db()
    client = TestClient(app)

    resp = client.get("/api/v1/config/debug/db")

    assert resp.status_code == 404


if __name__ == "__main__":
    test_saved_api_key_is_encrypted_but_returned_masked()
    test_masked_update_preserves_encrypted_key()
    test_legacy_plaintext_keys_are_migrated_on_init()
    test_config_debug_db_endpoint_is_not_available()
