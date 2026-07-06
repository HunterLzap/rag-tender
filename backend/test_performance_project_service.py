"""业绩项目库 CRUD 测试。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.services import performance_project_service


def test_performance_project_crud() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "performance_project.db")
        asyncio.run(_assert_crud())
    finally:
        tmp_dir.cleanup()


async def _assert_crud() -> None:
    await init_db()
    created = await performance_project_service.create_project(
        {
            "project_name": "智慧园区建设项目",
            "client_name": "某某有限公司",
            "contract_no": "HT-2024-001",
            "contract_amount": "120万元",
            "sign_date": "2024-03-01",
            "completion_date": "2024-10-01",
            "project_scope": "弱电智能化系统供货与安装",
            "year": "2024",
            "file_ids": [1, 2],
            "remark": "测试项目",
        }
    )
    assert created.id is not None
    assert created.project_name == "智慧园区建设项目"
    assert created.file_ids == [1, 2]

    projects = await performance_project_service.list_projects()
    assert len(projects) == 1

    updated = await performance_project_service.update_project(
        created.id,
        {"contract_amount": "150万元", "file_ids": [2]},
    )
    assert updated is not None
    assert updated.contract_amount == "150万元"
    assert updated.file_ids == [2]

    deleted = await performance_project_service.delete_project(created.id)
    assert deleted is True
    assert await performance_project_service.list_projects() == []


if __name__ == "__main__":
    test_performance_project_crud()
    print("performance project service tests passed")
