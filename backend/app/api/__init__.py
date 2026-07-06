"""API 路由聚合模块。

注册所有路由：config / tenders / knowledge / match / fill / technical / checklist / rules。
"""

from fastapi import APIRouter

from app.api.checklist_api import router as checklist_router
from app.api.config_api import router as config_router
from app.api.fill import router as fill_router
from app.api.knowledge import router as knowledge_router
from app.api.match import router as match_router
from app.api.performance import router as performance_router
from app.api.rules import router as rules_router
from app.api.technical_api import router as technical_router
from app.api.tenders import router as tenders_router

__all__ = [
    "config_router",
    "tenders_router",
    "knowledge_router",
    "match_router",
    "fill_router",
    "technical_router",
    "checklist_router",
    "performance_router",
    "rules_router",
]
