"""文件工具：文件类型识别、安全路径管理。"""

import os
import time
from typing import Optional

import filetype

from app.config import (
    KNOWLEDGE_UPLOAD_DIR,
    TENDER_UPLOAD_DIR,
    TEMPLATE_UPLOAD_DIR,
)


def detect_file_type(file_path: str) -> str:
    """识别文件类型。

    使用 filetype 库进行 magic number 识别，回退到扩展名判断。

    Args:
        file_path: 文件路径。

    Returns:
        文件类型字符串：``pdf`` / ``docx`` / ``xlsx`` / ``image`` / ``unknown``。
    """
    # 优先使用 filetype 库的 magic number 识别
    kind = filetype.guess(file_path)
    if kind is not None:
        mime = kind.mime
        if mime == "application/pdf":
            return "pdf"
        elif mime in (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
        ):
            return "docx"
        elif mime in (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        ):
            return "xlsx"
        elif mime.startswith("image/"):
            return "image"
        elif mime == "application/msword":
            return "doc"

    # 回退到扩展名判断
    ext = os.path.splitext(file_path)[1].lower()
    ext_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "doc",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".bmp": "image",
        ".tiff": "image",
        ".tif": "image",
    }
    return ext_map.get(ext, "unknown")


def safe_save_path(
    filename: str, category: str = "tenders"
) -> str:
    """生成安全的文件存储路径。

    文件名格式：``{timestamp}_{original_filename}``，避免文件名冲突。
    路径中的特殊字符会被清理。

    Args:
        filename: 原始文件名。
        category: 存储分类（``tenders`` / ``knowledge`` / ``templates``），
            knowledge 分类下可附加子目录名（如 ``knowledge/enterprise``）。

    Returns:
        安全的文件存储绝对路径。
    """
    timestamp = int(time.time())

    # 清理文件名中的危险字符
    safe_name = os.path.basename(filename)
    safe_name = safe_name.replace("..", "").replace("/", "").replace("\\", "")

    # 确定基础目录
    if category == "tenders":
        base_dir = TENDER_UPLOAD_DIR
    elif category == "templates":
        base_dir = TEMPLATE_UPLOAD_DIR
    elif category.startswith("knowledge"):
        # 支持 knowledge/enterprise 等子目录
        parts = category.split("/", 1)
        if len(parts) > 1:
            base_dir = os.path.join(KNOWLEDGE_UPLOAD_DIR, parts[1])
        else:
            base_dir = KNOWLEDGE_UPLOAD_DIR
    else:
        base_dir = KNOWLEDGE_UPLOAD_DIR

    os.makedirs(base_dir, exist_ok=True)
    final_name = f"{timestamp}_{safe_name}"
    return os.path.join(base_dir, final_name)


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写，含点号）。

    Args:
        filename: 文件名。

    Returns:
        小写扩展名，如 ``.pdf``。
    """
    return os.path.splitext(filename)[1].lower()


def ensure_dir(path: str) -> None:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径。
    """
    os.makedirs(path, exist_ok=True)
