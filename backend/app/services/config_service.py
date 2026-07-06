"""API 配置业务逻辑：CRUD + 测试连接 + 供应商预设。"""

import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import PROVIDER_PRESETS
from app.database import get_db
from app.models.config_model import ApiConfig
from app.utils.crypto import decrypt_secret, encrypt_secret, mask_stored_secret
from app.utils.mask import mask_in_log

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。

    Returns:
        ``YYYY-MM-DD HH:MM:SS`` 格式的时间字符串。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def get_all_configs() -> list[dict[str, Any]]:
    """获取所有活跃的 API 配置（Key 已脱敏）。

    从 SQLite 读取三组配置（LLM/Embedding/Vision），返回时 API Key 脱敏。

    Returns:
        配置列表，每个配置的 ``api_key`` 字段已脱敏（``****`` + 末 4 位）。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM api_configs ORDER BY config_type, is_active DESC, updated_at DESC"
        )
        rows = await cursor.fetchall()
        configs = []
        for row in rows:
            row_dict = dict(row)
            row_dict["api_key"] = mask_stored_secret(row_dict.get("api_key"))
            row_dict["is_active"] = bool(row_dict.get("is_active", 0))
            configs.append(row_dict)
        return configs
    finally:
        await db.close()


async def save_config(
    config_type: str,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    is_active: bool = True,
) -> dict[str, Any]:
    """保存或更新 API 配置。

    如果同 config_type 的配置已存在且 provider 相同，则更新；否则新增。
    保存时将同 config_type 的其他记录 is_active 置为 0（仅保留一个活跃）。

    Args:
        config_type: 配置类型（llm/embedding/vision）。
        provider: 供应商标识。
        base_url: API 基础 URL。
        api_key: API 密钥（明文传入，落库前加密）。
        model_name: 模型名称。
        is_active: 是否设为活跃配置。

    Returns:
        保存后的配置信息（api_key 已脱敏）。
    """
    now = _now_iso()
    db = await get_db()
    try:
        # 查找是否已有同 config_type 的配置
        cursor = await db.execute(
            "SELECT id, api_key FROM api_configs WHERE config_type = ? ORDER BY is_active DESC, updated_at DESC LIMIT 1",
            (config_type,),
        )
        existing = await cursor.fetchone()

        if existing:
            # 更新已有配置
            config_id = existing["id"]
            # 如果新 api_key 为空或为脱敏格式（****开头），保留原有 key
            old_key = existing["api_key"]
            if api_key is None or api_key == "" or api_key.startswith("****"):
                final_key = old_key
                logger.info(
                    "更新配置 config_type=%s, key=%s (保留原 Key)",
                    config_type,
                    mask_stored_secret(old_key),
                )
            else:
                final_key = encrypt_secret(api_key)
                logger.info(
                    "更新配置 config_type=%s, key=%s (新 Key)",
                    config_type,
                    mask_in_log(api_key),
                )

            await db.execute(
                """UPDATE api_configs 
                   SET provider = ?, base_url = ?, api_key = ?, model_name = ?, 
                       is_active = ?, updated_at = ?
                   WHERE id = ?""",
                (provider, base_url, final_key, model_name, int(is_active), now, config_id),
            )
            await db.commit()
            return {
                "id": config_id,
                "config_type": config_type,
                "provider": provider,
                "base_url": base_url,
                "api_key": mask_stored_secret(final_key),
                "model_name": model_name,
                "is_active": is_active,
                "updated_at": now,
            }
        else:
            # 新增配置
            logger.info(
                "新增配置 config_type=%s, key=%s",
                config_type,
                mask_in_log(api_key),
            )
            final_key = encrypt_secret(api_key)
            cursor = await db.execute(
                """INSERT INTO api_configs 
                   (config_type, provider, base_url, api_key, model_name, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (config_type, provider, base_url, final_key, model_name, int(is_active), now, now),
            )
            await db.commit()
            config_id = cursor.lastrowid
            return {
                "id": config_id,
                "config_type": config_type,
                "provider": provider,
                "base_url": base_url,
                "api_key": mask_stored_secret(final_key),
                "model_name": model_name,
                "is_active": is_active,
                "created_at": now,
                "updated_at": now,
            }
    finally:
        await db.close()


async def test_connection(
    config_type: str,
    base_url: str,
    api_key: str,
    model_name: str,
) -> dict[str, Any]:
    """测试 API 连接是否正常。

    根据 config_type 发送不同的测试请求：
    - LLM: 发送 chat/completions 请求（max_tokens=5）
    - Embedding: 发送 embeddings 请求
    - Vision: 发送 chat/completions 请求（纯文本，验证 Key 有效性）

    如果 api_key 为空或脱敏格式，自动从数据库读取已保存的 Key。

    Args:
        config_type: 配置类型（llm/embedding/vision）。
        base_url: API 基础 URL。
        api_key: API 密钥（可空，空时从 DB 取）。
        model_name: 模型名称。

    Returns:
        ``{"success": bool, "latency_ms": int, "message": str}``
    """
    # 如果 Key 为空或脱敏格式，从数据库获取已保存的 Key
    final_key = (api_key or "").strip()
    if not final_key or final_key.startswith("****"):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT api_key FROM api_configs WHERE config_type = ? ORDER BY updated_at DESC LIMIT 1",
                (config_type,),
            )
            row = await cursor.fetchone()
            if row:
                db_key = (row["api_key"] or "").strip()
                if db_key and not db_key.startswith("****"):
                    final_key = decrypt_secret(db_key) or ""
                    logger.info("从数据库获取 %s Key: %s", config_type, mask_in_log(final_key))
                else:
                    logger.warning("数据库 %s Key 无效: %s", config_type, mask_in_log(db_key))
        finally:
            await db.close()

    if not final_key or final_key.startswith("****"):
        return {
            "success": False,
            "latency_ms": 0,
            "message": f"未找到 {config_type} 的有效 API Key，请在设置中重新填写 Key 后保存",
        }
    logger.info(
        "测试连接: type=%s, base_url=%s, model=%s, key=%s",
        config_type,
        base_url,
        model_name,
        mask_in_log(final_key),
    )

    start_time = time.time()
    url = base_url.rstrip("/")

    try:
        if config_type == "llm":
            # 发送最小 chat 请求
            test_url = f"{url}/chat/completions"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
        elif config_type == "embedding":
            # 发送最小 embedding 请求
            test_url = f"{url}/embeddings"
            payload = {
                "model": model_name,
                "input": "test",
            }
        elif config_type == "vision":
            # 发送最小 chat 请求验证 Key 有效性
            test_url = f"{url}/chat/completions"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
        else:
            return {
                "success": False,
                "latency_ms": 0,
                "message": f"不支持的配置类型: {config_type}",
            }

        # 最终安全检查：strip + 拒绝空/脱敏
        final_key = (final_key or "").strip()
        if not final_key or final_key.startswith("****"):
            return {
                "success": False,
                "latency_ms": 0,
                "message": f"未找到 {config_type} 的有效 API Key，请在设置中重新填写 Key 后保存",
            }

        headers = {
            "Authorization": f"Bearer {final_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(test_url, json=payload, headers=headers)

        latency_ms = int((time.time() - start_time) * 1000)

        if resp.status_code == 200:
            logger.info("测试连接成功: type=%s, latency=%dms", config_type, latency_ms)
            return {
                "success": True,
                "latency_ms": latency_ms,
                "message": f"连接成功，延迟 {latency_ms}ms",
            }
        elif resp.status_code == 401:
            logger.warning("测试连接失败: Key 无效, type=%s", config_type)
            return {
                "success": False,
                "latency_ms": latency_ms,
                "message": f"API Key 无效（HTTP {resp.status_code}）",
            }
        elif resp.status_code == 404:
            logger.warning("测试连接失败: 模型不存在, type=%s, model=%s", config_type, model_name)
            return {
                "success": False,
                "latency_ms": latency_ms,
                "message": f"模型或端点不存在（HTTP {resp.status_code}），请检查 Base URL 和 Model",
            }
        else:
            # 尝试解析错误信息
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", resp.text[:200])
            except Exception:
                err_msg = resp.text[:200]
            logger.warning(
                "测试连接失败: type=%s, status=%d, msg=%s",
                config_type,
                resp.status_code,
                err_msg,
            )
            return {
                "success": False,
                "latency_ms": latency_ms,
                "message": f"连接失败（HTTP {resp.status_code}）: {err_msg}",
            }

    except httpx.ConnectError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error("测试连接失败（网络错误）: type=%s, error=%s", config_type, str(e))
        return {
            "success": False,
            "latency_ms": latency_ms,
            "message": f"网络连接失败: {str(e)}",
        }
    except httpx.TimeoutException:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error("测试连接失败（超时）: type=%s", config_type)
        return {
            "success": False,
            "latency_ms": latency_ms,
            "message": "连接超时（30秒），请检查网络或 Base URL",
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "测试连接失败（异常）: type=%s, error=%s, key=%s",
            config_type,
            str(e),
            mask_in_log(final_key),
        )
        return {
            "success": False,
            "latency_ms": latency_ms,
            "message": f"连接异常: {str(e)}",
        }


def get_presets() -> dict[str, dict[str, dict[str, str]]]:
    """获取供应商预设列表。

    返回 config.py 中定义的 PROVIDER_PRESETS，供前端下拉选择。

    Returns:
        供应商预设字典。
    """
    return PROVIDER_PRESETS


async def delete_config(config_id: int) -> bool:
    """根据 ID 删除一条 API 配置。

    Args:
        config_id: 配置记录的主键 ID。

    Returns:
        True 表示删除成功，False 表示记录不存在。
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM api_configs WHERE id = ?", (config_id,))
        existing = await cursor.fetchone()
        if not existing:
            return False
        await db.execute("DELETE FROM api_configs WHERE id = ?", (config_id,))
        await db.commit()
        logger.info("删除配置成功: id=%s", config_id)
        return True
    finally:
        await db.close()
