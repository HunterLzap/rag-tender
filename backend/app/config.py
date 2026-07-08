"""全局配置：路径常量、供应商预设、颜色常量。

所有路径基于 PROJECT_ROOT 推导，确保跨模块引用一致。
"""

import os
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

# 项目根目录（backend/ 的上级目录）
PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# backend 目录
BACKEND_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录（运行时生成，已加入 .gitignore）
DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")

# 上传文件根目录
UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")

# 标书上传目录
TENDER_UPLOAD_DIR: str = os.path.join(UPLOAD_DIR, "tenders")

# 知识库上传目录
KNOWLEDGE_UPLOAD_DIR: str = os.path.join(UPLOAD_DIR, "knowledge")

# 模板上传目录
TEMPLATE_UPLOAD_DIR: str = os.path.join(UPLOAD_DIR, "templates")

# 填写结果输出目录
OUTPUT_DIR: str = os.path.join(DATA_DIR, "output")

# RAG-Anything 工作目录
RAG_WORKSPACE_DIR: str = os.path.join(DATA_DIR, "rag_workspace")

# SQLite 数据库文件路径
DB_PATH: str = os.path.join(DATA_DIR, "tender_assistant.db")

# ---------------------------------------------------------------------------
# 应用常量
# ---------------------------------------------------------------------------

# 应用名称
APP_NAME: str = "RAG-Tender Assistant"

# 应用版本
APP_VERSION: str = "1.0.0"

# API 前缀
API_PREFIX: str = "/api/v1"

# 前端开发端口
FRONTEND_DEV_PORT: int = 5173

# 后端端口
BACKEND_PORT: int = 8000

# 文件大小上限（100 MB）
MAX_FILE_SIZE: int = 100 * 1024 * 1024

# 支持的标书文件格式
SUPPORTED_TENDER_FORMATS: list[str] = [".pdf", ".docx", ".doc"]

# 支持的知识库文件格式
SUPPORTED_KNOWLEDGE_FORMATS: list[str] = [
    ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".bmp", ".tiff",
]

# 支持的模板格式
SUPPORTED_TEMPLATE_FORMATS: list[str] = [".docx", ".pdf", ".xlsx"]

# LibreOffice 可执行文件路径
LIBREOFFICE_PATH: str = os.getenv(
    "LIBREOFFICE_PATH",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
)

# CORS 允许来源，逗号分隔。生产环境同源反代时通常不需要额外配置。
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "RAG_TENDER_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

# ---------------------------------------------------------------------------
# 供应商预设
# ---------------------------------------------------------------------------

# 供应商预设：每种供应商提供不同 config_type 的 base_url 和默认 model
PROVIDER_PRESETS: Dict[str, Dict[str, Dict[str, str]]] = {
    "deepseek": {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
        },
    },
    "siliconflow": {
        "embedding": {
            "base_url": "https://api.siliconflow.cn/v1",
            "model_name": "BAAI/bge-m3",
        },
        "vision": {
            "base_url": "https://api.siliconflow.cn/v1",
            "model_name": "Pro/Nex-N2-Pro",
        },
        "llm": {
            "base_url": "https://api.siliconflow.cn/v1",
            "model_name": "deepseek-ai/DeepSeek-V3",
        },
    },
    "zhipu": {
        "llm": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model_name": "glm-4-flash",
        },
        "embedding": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model_name": "embedding-3",
        },
        "vision": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model_name": "glm-4v-flash",
        },
    },
    "custom": {},
}

# ---------------------------------------------------------------------------
# 颜色常量（与前端 PRD 4.0 配色规范一致）
# ---------------------------------------------------------------------------

COLOR_PRIMARY: str = "#7C4DFF"
COLOR_PRIMARY_LIGHT: str = "#EDE7F6"
COLOR_BACKGROUND: str = "#FFFFFF"
COLOR_SURFACE: str = "#F9F7FF"
COLOR_SUCCESS: str = "#4CAF50"
COLOR_WARNING: str = "#FF9800"
COLOR_ERROR: str = "#EF5350"
COLOR_TEXT_PRIMARY: str = "#333333"
COLOR_TEXT_SECONDARY: str = "#666666"


def ensure_directories() -> None:
    """确保所有运行时目录存在，不存在则创建。"""
    dirs = [
        DATA_DIR,
        UPLOAD_DIR,
        TENDER_UPLOAD_DIR,
        KNOWLEDGE_UPLOAD_DIR,
        TEMPLATE_UPLOAD_DIR,
        OUTPUT_DIR,
        RAG_WORKSPACE_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
