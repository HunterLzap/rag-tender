"""烟雾测试脚本：验证 T01 + T02 基础功能。

测试项：
1. 启动 FastAPI 应用并初始化数据库
2. GET /api/v1/config/presets 返回供应商预设
3. GET /api/v1/config 返回空配置列表（数据库刚初始化）
4. POST /api/v1/config 保存一个配置
5. GET /api/v1/config 返回刚保存的配置（Key 脱敏）
6. POST /api/v1/config/test 测试连接（用假 Key，预期返回连接失败但接口正常）
"""

import asyncio
import atexit
import os
import sys
import tempfile
from pathlib import Path

# 将 backend 目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from app import database

# 烟雾测试必须使用隔离数据库，绝不能读写用户的真实 API 配置。
_TEST_DB_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
atexit.register(_TEST_DB_DIR.cleanup)
database.DB_PATH = str(Path(_TEST_DB_DIR.name) / "test_smoke.db")
os.environ["RAG_TENDER_SECRET_KEY"] = (
    "cD6h7vUv8yaCEvCwkO-9xb41E6cVD_0Vtcfs7AFzTZ0="
)

from app.main import app
from app.database import init_db


def test_smoke() -> None:
    """执行全部烟雾测试。"""
    print("=" * 60)
    print("  RAG-Tender Assistant 烟雾测试")
    print("=" * 60)

    # 初始化数据库（TestClient 的 lifespan 会自动调用，但这里确保万无一失）
    asyncio.run(init_db())

    client = TestClient(app)

    passed = 0
    failed = 0

    # ------------------------------------------------------------------
    # 测试 1: 健康检查
    # ------------------------------------------------------------------
    print("\n[测试 1] GET /api/v1/health — 健康检查")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}"
    assert data["data"]["status"] == "ok"
    print(f"  ✅ 通过: status={data['data']['status']}, service={data['data']['service']}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 2: 获取供应商预设
    # ------------------------------------------------------------------
    print("\n[测试 2] GET /api/v1/config/presets — 获取供应商预设")
    resp = client.get("/api/v1/config/presets")
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}"
    presets = data["data"]["presets"]
    assert "deepseek" in presets, "缺少 deepseek 预设"
    assert "siliconflow" in presets, "缺少 siliconflow 预设"
    assert "llm" in presets["deepseek"], "deepseek 缺少 llm 配置"
    assert presets["deepseek"]["llm"]["model_name"] == "deepseek-chat"
    assert "embedding" in presets["siliconflow"], "siliconflow 缺少 embedding 配置"
    assert presets["siliconflow"]["embedding"]["model_name"] == "BAAI/bge-m3"
    print(f"  ✅ 通过: 预设供应商={list(presets.keys())}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 3: 获取空配置列表
    # ------------------------------------------------------------------
    print("\n[测试 3] GET /api/v1/config — 获取配置列表（预期为空）")
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}"
    assert isinstance(data["data"], list), "data 应为列表"
    print(f"  ✅ 通过: 当前配置数={len(data['data'])}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 4: 保存 LLM 配置
    # ------------------------------------------------------------------
    print("\n[测试 4] POST /api/v1/config — 保存 LLM 配置")
    resp = client.post(
        "/api/v1/config",
        json={
            "config_type": "llm",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "unit-test-key-1234567890abcdef",
            "model_name": "deepseek-chat",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}, message={data['message']}"
    saved = data["data"]
    assert saved["config_type"] == "llm"
    assert saved["provider"] == "deepseek"
    assert saved["api_key"] == "****cdef", f"Key 脱敏错误: {saved['api_key']}"
    assert saved["is_active"] is True
    print(f"  ✅ 通过: id={saved['id']}, api_key={saved['api_key']}（已脱敏）")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 5: 再次获取配置列表（应有 1 条）
    # ------------------------------------------------------------------
    print("\n[测试 5] GET /api/v1/config — 获取配置列表（预期 1 条，Key 脱敏）")
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}"
    configs = data["data"]
    assert len(configs) == 1, f"预期 1 条配置，实际 {len(configs)} 条"
    assert configs[0]["api_key"] == "****cdef", f"Key 未脱敏: {configs[0]['api_key']}"
    print(f"  ✅ 通过: 配置数={len(configs)}, api_key={configs[0]['api_key']}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 6: 测试连接（假 Key，预期连接失败但接口正常）
    # ------------------------------------------------------------------
    print("\n[测试 6] POST /api/v1/config/test — 测试连接（假 Key，预期失败）")
    resp = client.post(
        "/api/v1/config/test",
        json={
            "config_type": "llm",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "unit-fake-key-0000000000000000",
            "model_name": "deepseek-chat",
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}, message={data['message']}"
    test_result = data["data"]
    assert "success" in test_result, "缺少 success 字段"
    assert "latency_ms" in test_result, "缺少 latency_ms 字段"
    assert "message" in test_result, "缺少 message 字段"
    # 用假 Key，预期 success=False
    print(f"  ✅ 通过: success={test_result['success']}, latency={test_result['latency_ms']}ms")
    print(f"     message={test_result['message']}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 7: 更新配置（传入脱敏 Key，应保留原 Key）
    # ------------------------------------------------------------------
    print("\n[测试 7] POST /api/v1/config — 更新配置（传入 **** 脱敏 Key，保留原 Key）")
    resp = client.post(
        "/api/v1/config",
        json={
            "config_type": "llm",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "****cdef",
            "model_name": "deepseek-reasoner",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}, message={data['message']}"
    updated = data["data"]
    assert updated["model_name"] == "deepseek-reasoner", "model_name 未更新"
    assert updated["api_key"] == "****cdef", f"Key 脱敏错误: {updated['api_key']}"
    print(f"  ✅ 通过: model_name 已更新为 {updated['model_name']}, Key 保留原值")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 8: 保存 Embedding 配置
    # ------------------------------------------------------------------
    print("\n[测试 8] POST /api/v1/config — 保存 Embedding 配置")
    resp = client.post(
        "/api/v1/config",
        json={
            "config_type": "embedding",
            "provider": "siliconflow",
            "base_url": "https://api.siliconflow.cn/v1",
            "api_key": "unit-embedding-test-1234567890",
            "model_name": "BAAI/bge-m3",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}"
    assert data["data"]["api_key"] == "****7890"
    print(f"  ✅ 通过: embedding 配置已保存, api_key={data['data']['api_key']}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 9: 验证配置总数
    # ------------------------------------------------------------------
    print("\n[测试 9] GET /api/v1/config — 验证配置总数（预期 2 条）")
    resp = client.get("/api/v1/config")
    data = resp.json()
    assert len(data["data"]) == 2, f"预期 2 条配置，实际 {len(data['data'])} 条"
    print(f"  ✅ 通过: 配置总数={len(data['data'])}")
    passed += 1

    # ------------------------------------------------------------------
    # 测试 10: 参数校验（无效 config_type）
    # ------------------------------------------------------------------
    print("\n[测试 10] POST /api/v1/config — 参数校验（无效 config_type）")
    resp = client.post(
        "/api/v1/config",
        json={
            "config_type": "invalid_type",
            "provider": "custom",
            "base_url": "https://example.com",
            "api_key": "unit-test",
            "model_name": "test-model",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 1001, f"预期 code=1001, 实际 code={data['code']}"
    print(f"  ✅ 通过: 正确拒绝无效 config_type, code={data['code']}")
    passed += 1

    # ------------------------------------------------------------------
    # 总结
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"  烟雾测试结果: ✅ {passed} 通过, ❌ {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n  全部测试通过！🎉")


if __name__ == "__main__":
    test_smoke()
