"""API 配置数据模型：ApiConfig。

对应 SQLite 表 api_configs。
"""

from typing import Optional

from pydantic import BaseModel


class ApiConfig(BaseModel):
    """API 配置模型，对应 api_configs 表。

    存储三组 API 配置（LLM/Embedding/Vision），支持运行时切换。

    Attributes:
        id: 主键，自增。
        config_type: 配置类型（llm/embedding/vision）。
        provider: 供应商标识（deepseek/siliconflow/zhipu/custom）。
        base_url: API 基础 URL。
        api_key: API 密钥（加密存储，返回时脱敏）。
        model_name: 模型名称。
        is_active: 是否为当前活跃配置（同类型仅一个为 True）。
        created_at: 记录创建时间（ISO 8601）。
        updated_at: 记录更新时间（ISO 8601）。
    """

    id: Optional[int] = None
    config_type: str = ""
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
