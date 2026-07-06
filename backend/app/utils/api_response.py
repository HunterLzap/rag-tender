"""统一响应工具函数。

提供快捷构造 ApiResponse 的辅助函数和错误码常量。
"""

from typing import Any, Optional

from app.schemas.common import ApiResponse


# ---------------------------------------------------------------------------
# 错误码定义（ARCHITECTURE.md 7.2 节）
# ---------------------------------------------------------------------------

class ErrorCode:
    """错误码常量。"""

    SUCCESS = 0
    PARAM_VALIDATION_FAILED = 1001
    FILE_FORMAT_UNSUPPORTED = 1002
    FILE_SIZE_EXCEEDED = 1003
    API_CONFIG_NOT_FOUND = 2001
    API_CONNECTION_FAILED = 2002
    API_KEY_INVALID = 2003
    TENDER_PARSE_FAILED = 3001
    KNOWLEDGE_PARSE_FAILED = 3002
    MATCH_EXECUTION_FAILED = 3003
    AUTO_FILL_FAILED = 4001
    LIBREOFFICE_CONVERT_FAILED = 4002
    INTERNAL_SERVER_ERROR = 5001


# 错误码 → 默认消息映射
_ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.PARAM_VALIDATION_FAILED: "参数校验失败",
    ErrorCode.FILE_FORMAT_UNSUPPORTED: "文件格式不支持",
    ErrorCode.FILE_SIZE_EXCEEDED: "文件大小超限（>100MB）",
    ErrorCode.API_CONFIG_NOT_FOUND: "API 配置未找到",
    ErrorCode.API_CONNECTION_FAILED: "API 连接失败",
    ErrorCode.API_KEY_INVALID: "API Key 无效",
    ErrorCode.TENDER_PARSE_FAILED: "标书解析失败",
    ErrorCode.KNOWLEDGE_PARSE_FAILED: "知识库解析失败",
    ErrorCode.MATCH_EXECUTION_FAILED: "匹配执行失败",
    ErrorCode.AUTO_FILL_FAILED: "自动填写失败",
    ErrorCode.LIBREOFFICE_CONVERT_FAILED: "LibreOffice 转换失败",
    ErrorCode.INTERNAL_SERVER_ERROR: "内部服务器错误",
}


def get_error_message(code: int) -> str:
    """获取错误码对应的默认消息。

    Args:
        code: 错误码。

    Returns:
        默认错误消息，未知的错误码返回 "未知错误"。
    """
    return _ERROR_MESSAGES.get(code, "未知错误")


def success_response(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    Args:
        data: 响应数据。
        message: 响应消息。

    Returns:
        ``{"code": 0, "data": data, "message": message}`` 字典。
    """
    return {"code": ErrorCode.SUCCESS, "data": data, "message": message}


def error_response(code: int, message: Optional[str] = None) -> dict:
    """构造错误响应字典。

    Args:
        code: 错误码（非 0）。
        message: 自定义错误消息，为 None 时使用默认消息。

    Returns:
        ``{"code": code, "data": None, "message": message}`` 字典。
    """
    return {
        "code": code,
        "data": None,
        "message": message or get_error_message(code),
    }
