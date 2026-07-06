"""API 配置相关 Pydantic schema。"""

from typing import Dict, Optional

from pydantic import BaseModel


class ApiConfigCreate(BaseModel):
    """创建/更新 API 配置的请求体。

    Attributes:
        config_type: 配置类型（llm/embedding/vision）。
        provider: 供应商标识。
        base_url: API 基础 URL。
        api_key: API 密钥（明文传入，落库前加密，返回时脱敏）。
        model_name: 模型名称。
        is_active: 是否设为活跃配置。
    """

    config_type: str
    provider: Optional[str] = "custom"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool = True


class ApiConfigResponse(BaseModel):
    """API 配置响应体（api_key 已脱敏）。

    Attributes:
        id: 配置 ID。
        config_type: 配置类型。
        provider: 供应商标识。
        base_url: API 基础 URL。
        api_key: 脱敏后的 API Key（**** + 末 4 位）。
        model_name: 模型名称。
        is_active: 是否活跃。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: Optional[int] = None
    config_type: str
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """测试 API 连接的请求体。

    Attributes:
        config_type: 配置类型（llm/embedding/vision）。
        base_url: API 基础 URL。
        api_key: API 密钥。
        model_name: 模型名称。
    """

    config_type: str
    base_url: str
    api_key: str
    model_name: str


class TestConnectionResponse(BaseModel):
    """测试 API 连接的响应体。

    Attributes:
        success: 连接是否成功。
        latency_ms: 请求延迟（毫秒）。
        message: 结果消息。
    """

    success: bool
    latency_ms: int
    message: str


class ProviderPresetResponse(BaseModel):
    """供应商预设响应体。

    Attributes:
        presets: 供应商预设字典，按供应商名分组，每组含各 config_type 的 base_url 和 model_name。
    """

    presets: Dict[str, Dict[str, Dict[str, str]]]
