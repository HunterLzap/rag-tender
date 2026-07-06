"""数据模型包，导出所有模型类。

模型使用 Pydantic BaseModel，字段与 SQLite 表一一对应。
"""

from app.models.config_model import ApiConfig
from app.models.knowledge import KnowledgeFile, Qualification
from app.models.match import MatchResult
from app.models.tender import Tender, TenderRequirement
from app.models.template import FillTemplate

__all__ = [
    "Tender",
    "TenderRequirement",
    "KnowledgeFile",
    "Qualification",
    "MatchResult",
    "ApiConfig",
    "FillTemplate",
]
