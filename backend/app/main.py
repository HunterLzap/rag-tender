"""FastAPI 应用入口 — RAG-Tender Assistant。

负责创建 FastAPI 实例、配置 CORS、注册路由、定义启动事件。
"""

import os
import sys

# 确保本虚拟环境 Scripts 在 PATH 中，供 LibreOffice/辅助命令查找。
_SCRIPTS_DIR = os.path.join(os.path.dirname(sys.executable), "Scripts")
if os.path.isdir(_SCRIPTS_DIR) and _SCRIPTS_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _SCRIPTS_DIR + os.pathsep + os.environ.get("PATH", "")

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import API_PREFIX, APP_NAME, APP_VERSION
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时初始化数据库。"""
    await init_db()
    yield


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="标书自动分析辅助系统后端 API",
        lifespan=lifespan,
    )

    # CORS 配置：允许前端开发端口访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from app.api import (
        checklist_router,
        config_router,
        fill_router,
        knowledge_router,
        match_router,
        performance_router,
        rules_router,
        technical_router,
        tenders_router,
    )
    app.include_router(config_router, prefix=API_PREFIX)
    app.include_router(tenders_router, prefix=API_PREFIX)
    app.include_router(knowledge_router, prefix=API_PREFIX)
    app.include_router(match_router, prefix=API_PREFIX)
    app.include_router(fill_router, prefix=API_PREFIX)
    app.include_router(technical_router, prefix=API_PREFIX)
    app.include_router(checklist_router, prefix=API_PREFIX)
    app.include_router(performance_router, prefix=API_PREFIX)
    app.include_router(rules_router, prefix=API_PREFIX)

    # 健康检查端点
    @app.get(f"{API_PREFIX}/health")
    async def health_check() -> dict:
        """健康检查端点。"""
        return {
            "code": 0,
            "data": {"status": "ok", "service": APP_NAME, "version": APP_VERSION},
            "message": "success",
        }

    # 根路径重定向到文档
    @app.get("/")
    async def root() -> dict:
        """根路径，返回 API 信息。"""
        return {
            "code": 0,
            "data": {"docs": "/docs", "health": f"{API_PREFIX}/health"},
            "message": "success",
        }

    return app


# 全局应用实例
app = create_app()
