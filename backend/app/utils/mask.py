"""API Key 脱敏工具。

确保 API Key 在 API 返回和日志中不暴露明文。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def mask_key(key: Optional[str]) -> Optional[str]:
    """脱敏 API Key，仅保留末 4 位。

    Examples:
        >>> mask_key("unit-secret-abcdef1234567890")
        '****7890'
        >>> mask_key("ab")
        '****'
        >>> mask_key(None)
        None

    Args:
        key: 原始 API Key。

    Returns:
        脱敏后的 Key，格式为 ``****`` + 末 4 位。
    """
    if key is None:
        return None
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def mask_in_log(key: Optional[str]) -> str:
    """日志中完全隐藏 API Key。

    所有日志输出中 API Key 替换为 ``[REDACTED]``，不输出任何明文片段。

    Args:
        key: 原始 API Key（仅用于判断是否非空）。

    Returns:
        固定字符串 ``[REDACTED]`` 或 ``[EMPTY]``。
    """
    if key is None or key == "":
        return "[EMPTY]"
    return "[REDACTED]"


class RedactingFormatter(logging.Formatter):
    """日志格式化器，自动替换日志中的 API Key 片段。

    将日志消息中疑似 API Key 的模式（sk- 开头、长度 > 10 的连续字符）
    替换为 ``[REDACTED]``，防止意外泄露。
    """

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        # 简单策略：替换 sk- 开头的长字符串
        import re
        message = re.sub(r"sk-[A-Za-z0-9]{8,}", "[REDACTED]", message)
        return message
