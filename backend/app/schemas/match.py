"""匹配相关 Pydantic schema。"""

from typing import Optional

from pydantic import BaseModel

from app.models.match import MatchResult


class MatchResultResponse(MatchResult):
    """匹配结果响应（继承 MatchResult 模型）。"""

    pass


class MatchConfirmRequest(BaseModel):
    """匹配结果人工确认请求体（P1-02）。

    Attributes:
        confirmed_status: 人工确认状态（confirmed/rejected）。
    """

    confirmed_status: str
    correction_reason: Optional[str] = None
