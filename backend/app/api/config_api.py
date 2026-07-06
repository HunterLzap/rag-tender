"""API 配置路由：CRUD + 测试连接 + 供应商预设。

所有端点前缀为 ``/config``，由 main.py 挂载到 ``/api/v1`` 下。
"""

import logging

from fastapi import APIRouter

from app.schemas.config_schema import (
    ApiConfigCreate,
    ApiConfigResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services import config_service
from app.utils.api_response import error_response, success_response
from app.utils.mask import mask_in_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["API 配置"])


@router.get("", summary="获取所有 API 配置")
async def get_configs() -> dict:
    """获取所有 API 配置列表。

    返回所有已保存的 API 配置，api_key 字段已脱敏（**** + 末 4 位）。

    Returns:
        统一响应，data 为配置列表。
    """
    try:
        configs = await config_service.get_all_configs()
        return success_response(data=configs)
    except Exception as e:
        logger.error("获取 API 配置失败: %s", str(e))
        return error_response(5001, f"获取配置失败: {str(e)}")


@router.post("", summary="保存/更新 API 配置")
async def save_config(config: ApiConfigCreate) -> dict:
    """保存或更新 API 配置。

    根据 config_type 保存配置。如果 api_key 为空或为脱敏格式（****开头），
    则保留原有 Key 不变。

    Args:
        config: API 配置请求体。

    Returns:
        统一响应，data 为保存后的配置信息（api_key 已脱敏）。
    """
    try:
        # 校验 config_type
        valid_types = {"llm", "embedding", "vision"}
        if config.config_type not in valid_types:
            return error_response(1001, f"config_type 必须是 {valid_types} 之一")

        logger.info(
            "保存 API 配置: type=%s, provider=%s, key=%s",
            config.config_type,
            config.provider,
            mask_in_log(config.api_key),
        )

        result = await config_service.save_config(
            config_type=config.config_type,
            provider=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            model_name=config.model_name,
            is_active=config.is_active,
        )
        return success_response(data=result, message="配置保存成功")
    except Exception as e:
        logger.error("保存 API 配置失败: %s", str(e))
        return error_response(5001, f"保存配置失败: {str(e)}")


@router.post("/test", summary="测试 API 连接")
async def test_connection(req: TestConnectionRequest) -> dict:
    """测试 API 连接是否正常。

    根据 config_type 发送最小请求验证 Key 和端点有效性。

    Args:
        req: 测试连接请求体。

    Returns:
        统一响应，data 为 ``{"success": bool, "latency_ms": int, "message": str}``。
    """
    try:
        # 校验 config_type
        valid_types = {"llm", "embedding", "vision"}
        if req.config_type not in valid_types:
            return error_response(1001, f"config_type 必须是 {valid_types} 之一")

        logger.info(
            "测试连接请求: type=%s, base_url=%s, model=%s, key_raw='%s'",
            req.config_type,
            req.base_url,
            req.model_name,
            mask_in_log(req.api_key),
        )

        result = await config_service.test_connection(
            config_type=req.config_type,
            base_url=req.base_url,
            api_key=req.api_key,
            model_name=req.model_name,
        )
        return success_response(data=result)
    except Exception as e:
        logger.error(
            "测试连接异常: type=%s, error=%s, key=%s",
            req.config_type,
            str(e),
            mask_in_log(req.api_key),
        )
        return error_response(2002, f"测试连接异常: {str(e)}")

@router.get("/presets", summary="获取供应商预设")
async def get_presets() -> dict:
    """获取供应商预设列表。

    返回 DeepSeek、硅基流动、智谱等供应商的预设 base_url 和默认 model_name。

    Returns:
        统一响应，data 为 ``{"presets": {...}}`` 供应商预设字典。
    """
    try:
        presets = config_service.get_presets()
        return success_response(data={"presets": presets})
    except Exception as e:
        logger.error("获取供应商预设失败: %s", str(e))
        return error_response(5001, f"获取预设失败: {str(e)}")


@router.delete("/{config_id}", summary="删除 API 配置")
async def delete_config(config_id: int) -> dict:
    """根据 ID 删除一条 API 配置。

    Args:
        config_id: 配置记录的主键 ID。

    Returns:
        统一响应，data 为 ``{"deleted": bool}``。
    """
    try:
        logger.info("删除 API 配置: id=%s", config_id)
        deleted = await config_service.delete_config(config_id)
        if not deleted:
            return error_response(4004, f"配置不存在: id={config_id}")
        return success_response(data={"deleted": True}, message="配置已删除")
    except Exception as e:
        logger.error("删除 API 配置失败: id=%s, error=%s", config_id, str(e))
        return error_response(5001, f"删除配置失败: {str(e)}")
