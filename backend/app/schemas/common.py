"""统一响应格式 schema。

所有 API 返回 ``{code, data, message}`` 结构，code=0 表示成功。
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    Attributes:
        code: 状态码，0=成功，非 0=错误码。
        data: 响应数据。
        message: 响应消息。
    """

    code: int = 0
    data: Optional[T] = None
    message: str = "success"
