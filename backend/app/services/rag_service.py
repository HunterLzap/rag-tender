"""RAG-Anything 封装服务：初始化、文档解析、语义查询。

从 SQLite 读取活跃的 API 配置（LLM/Embedding/Vision），动态构建
RAGAnything 实例。每标书独立工作目录，知识库共享工作目录。
API 配置变更时可通过 rebuild_instance() 重建实例。
"""

import functools
import logging
import os
import pathlib
import subprocess
import sys
from typing import Any, Callable, Optional

from app.config import RAG_WORKSPACE_DIR
from app.database import get_db
from app.models.config_model import ApiConfig
from app.utils.crypto import decrypt_secret
from app.utils.llm_helpers import build_embedding_func, build_llm_func, build_vision_func
from app.utils.mask import mask_in_log

logger = logging.getLogger(__name__)

_MINERU_EXE: Optional[str] = None
_MINERU_PATCHED = False
_RAG_IMPORTS: Optional[tuple[Any, Any, Any]] = None
_RAG_IMPORT_ERROR: Optional[Exception] = None


def _patch_mineru_cli() -> None:
    """仅在真正创建 RAGAnything 实例时 patch mineru CLI。"""
    global _MINERU_EXE, _MINERU_PATCHED
    if _MINERU_PATCHED:
        return
    _MINERU_PATCHED = True

    for scripts_dir in (
        pathlib.Path(sys.prefix) / "Scripts",
        pathlib.Path(sys.exec_prefix) / "Scripts" if hasattr(sys, "exec_prefix") else None,
    ):
        if scripts_dir is None:
            continue
        candidate = scripts_dir / "mineru.exe"
        if not candidate.is_file():
            continue

        _MINERU_EXE = str(candidate)
        orig_popen = subprocess.Popen

        @functools.wraps(orig_popen)
        def _popen_patched(args, *a, **kw):
            if isinstance(args, (list, tuple)) and args and args[0] == "mineru":
                args = [_MINERU_EXE] + list(args[1:])
                # txt 方法 + 未指定 backend 时，强制 --backend pipeline 跳过 VLM
                has_txt = any(
                    args[i] == "-m" and i + 1 < len(args) and args[i + 1] == "txt"
                    for i in range(len(args) - 1)
                )
                has_backend = any(
                    args[i] in ("-b", "--backend") for i in range(len(args) - 1)
                )
                if has_txt and not has_backend:
                    for i in range(len(args) - 1):
                        if args[i] == "-m" and i + 1 < len(args) and args[i + 1] == "txt":
                            args = list(args[: i + 2]) + ["-b", "pipeline"] + list(args[i + 2 :])
                            break
            return orig_popen(args, *a, **kw)

        subprocess.Popen = _popen_patched
        logger.info("mineru CLI 已 patch: %s", _MINERU_EXE)
        return

    logger.warning("未找到 mineru.exe，RAG-Anything 的 mineru 解析不可用")


def _get_rag_imports() -> tuple[Any, Any, Any]:
    """懒加载 RAG-Anything，避免普通 LLM/Vision/解析链路触发旧解析依赖。"""
    global _RAG_IMPORTS, _RAG_IMPORT_ERROR
    if _RAG_IMPORTS is not None:
        return _RAG_IMPORTS
    if _RAG_IMPORT_ERROR is not None:
        raise RuntimeError(
            "RAG-Anything 未安装，无法创建实例。请确保 raganything 和 lightrag-hku 已安装。"
        ) from _RAG_IMPORT_ERROR

    try:
        from raganything import RAGAnything, RAGAnythingConfig
        from lightrag.utils import EmbeddingFunc
    except ImportError as e:
        _RAG_IMPORT_ERROR = e
        raise RuntimeError(
            "RAG-Anything 未安装，无法创建实例。请确保 raganything 和 lightrag-hku 已安装。"
        ) from e

    _RAG_IMPORTS = (RAGAnything, RAGAnythingConfig, EmbeddingFunc)
    return _RAG_IMPORTS


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def _get_active_config(config_type: str) -> Optional[ApiConfig]:
    """从 SQLite 读取指定类型的活跃 API 配置。

    Args:
        config_type: 配置类型（llm/embedding/vision）。

    Returns:
        ApiConfig 实例，未找到时返回 None。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM api_configs WHERE config_type = ? AND is_active = 1 "
            "ORDER BY updated_at DESC LIMIT 1",
            (config_type,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        row_dict = dict(row)
        row_dict["is_active"] = bool(row_dict.get("is_active", 0))
        row_dict["api_key"] = decrypt_secret(row_dict.get("api_key"))
        return ApiConfig(**row_dict)
    finally:
        await db.close()


async def get_llm_func() -> Callable:
    """获取当前活跃的 LLM 异步函数。

    从数据库读取 LLM 配置，使用 llm_helpers 构建可调用的异步函数。

    Returns:
        async def(prompt: str, **kwargs) -> str 的 LLM 函数。

    Raises:
        ValueError: LLM 配置未找到时抛出。
    """
    config = await _get_active_config("llm")
    if config is None:
        raise ValueError("LLM API 配置未找到，请先在设置中配置 LLM API")
    logger.info(
        "获取 LLM 函数: provider=%s, model=%s, key=%s",
        config.provider,
        config.model_name,
        mask_in_log(config.api_key),
    )
    return build_llm_func(config)


async def get_vision_func() -> Callable:
    """获取当前活跃的 Vision 异步函数。

    Returns:
        async def(image_base64: str, prompt: str) -> str 的 Vision 函数。

    Raises:
        ValueError: Vision 配置未找到时抛出。
    """
    config = await _get_active_config("vision")
    if config is None:
        raise ValueError("Vision API 配置未找到，请先在设置中配置 Vision API")
    logger.info(
        "获取 Vision 函数: provider=%s, model=%s",
        config.provider,
        config.model_name,
    )
    return build_vision_func(config)


class RAGService:
    """RAG-Anything 封装服务，单例模式管理 RAGAnything 实例。

    每个标书/知识库使用独立的工作目录，实例按工作目录缓存。
    API 配置变更时调用 rebuild_instance() 清除缓存。
    """

    _instance: Optional["RAGService"] = None
    _rag_instances: dict[str, Any]  # key: working_dir, value: RAGAnything
    _config_snapshot: Optional[str] = None  # 用于检测配置变更

    def __new__(cls) -> "RAGService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._rag_instances = {}
            cls._instance._config_snapshot = None
        return cls._instance

    def _get_working_dir(self, tender_id: Optional[int]) -> str:
        """获取 RAG 工作目录路径。

        Args:
            tender_id: 标书 ID，None 表示知识库共享目录。

        Returns:
            工作目录绝对路径。
        """
        subdir = str(tender_id) if tender_id is not None else "knowledge"
        working_dir = os.path.join(RAG_WORKSPACE_DIR, subdir)
        os.makedirs(working_dir, exist_ok=True)
        return working_dir

    async def _get_config_snapshot(self) -> str:
        """生成当前 API 配置的快照标识，用于检测配置是否变更。

        Returns:
            配置快照字符串。
        """
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT config_type, model_name, base_url, updated_at "
                "FROM api_configs WHERE is_active = 1 ORDER BY config_type"
            )
            rows = await cursor.fetchall()
            return "|".join(
                f"{r['config_type']}:{r['model_name']}:{r['base_url']}:{r['updated_at']}"
                for r in rows
            )
        finally:
            await db.close()

    async def get_rag_instance(
        self,
        tender_id: Optional[int] = None,
        enable_image: bool = False,
        enable_table: bool = False,
    ) -> Any:
        """获取或创建 RAGAnything 实例。

        根据 tender_id 确定工作目录，从 SQLite 读取活跃 API 配置，
        构建 LLM 和 Embedding 函数，创建 RAGAnything 实例并缓存。

        Args:
            tender_id: 标书 ID，None 表示知识库共享工作目录。
            enable_image: 是否启用图片识别（VLM）。
            enable_table: 是否启用表格识别。

        Returns:
            RAGAnything 实例。

        Raises:
            RuntimeError: RAG-Anything 未安装或配置缺失时抛出。
        """
        RAGAnything, RAGAnythingConfig, EmbeddingFunc = _get_rag_imports()
        _patch_mineru_cli()

        # 不同 VLM 配置用不同工作目录（如 4/ 和 4_vlm/），避免向量库冲突
        base_dir = self._get_working_dir(tender_id)
        working_dir = base_dir if not (enable_image or enable_table) else os.path.join(base_dir, "_vlm_retry")
        os.makedirs(working_dir, exist_ok=True)

        # 检查配置是否变更
        current_snapshot = await self._get_config_snapshot()
        if self._config_snapshot is not None and current_snapshot != self._config_snapshot:
            logger.info("API 配置已变更，清除 RAG 实例缓存")
            self._rag_instances.clear()
        self._config_snapshot = current_snapshot

        # 返回缓存的实例（按 working_dir 缓存）
        if working_dir in self._rag_instances:
            return self._rag_instances[working_dir]

        # 读取 API 配置
        llm_config = await _get_active_config("llm")
        embedding_config = await _get_active_config("embedding")

        if llm_config is None:
            raise RuntimeError("LLM API 配置未找到，请先在设置中配置 LLM API")
        if embedding_config is None:
            raise RuntimeError("Embedding API 配置未找到，请先在设置中配置 Embedding API")

        logger.info(
            "创建 RAGAnything 实例: working_dir=%s, llm_model=%s, emb_model=%s, vlm=%s",
            working_dir,
            llm_config.model_name,
            embedding_config.model_name,
            (enable_image or enable_table),
        )

        # 构建 LLM 函数
        llm_model_func = build_llm_func(llm_config)

        # 构建 Embedding 函数（用 lightrag 的 EmbeddingFunc 包装）
        raw_embedding_func = build_embedding_func(embedding_config)
        embedding_func = EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=8192,
            func=raw_embedding_func,
        )

        # 构建 RAGAnything 配置
        # 文本模式: parser="docling" 纯文本提取（不需要 VLM）
        # VLM 兜底: parser="mineru" 完整识别（需要 GPU）
        parser_name = "docling" if not (enable_image or enable_table) else "mineru"
        config = RAGAnythingConfig(
            working_dir=working_dir,
            parser=parser_name,
            parse_method="txt" if not (enable_image or enable_table) else "auto",
            enable_image_processing=enable_image,
            enable_table_processing=enable_table,
        )

        # 创建 RAGAnything 实例
        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
        )

        self._rag_instances[working_dir] = rag
        logger.info("RAGAnything 实例创建成功: %s", working_dir)
        return rag

    async def parse_document(
        self, file_path: str, tender_id: Optional[int] = None,
        enable_image: bool = False, enable_table: bool = False,
    ) -> dict:
        """调用 RAGAnything 解析文档。

        将文件路径传入 RAGAnything 的 process_document_complete 方法，
        完成文档解析、分块、向量化入库。

        Args:
            file_path: 待解析文件路径（PDF 格式）。
            tender_id: 标书 ID，None 表示知识库文件。
            enable_image: 是否启用图片识别（VLM）。
            enable_table: 是否启用表格识别。

        Returns:
            解析结果字典，包含文档内容和分块信息。

        Raises:
            RuntimeError: 解析失败时抛出。
        """
        rag = await self.get_rag_instance(tender_id, enable_image=enable_image, enable_table=enable_table)
        logger.info("开始解析文档: file=%s, tender_id=%s, vlm=%s", file_path, tender_id, enable_image or enable_table)
        try:
            result = await rag.process_document_complete(file_path)
            logger.info("文档解析完成: file=%s", file_path)
            if result is None:
                return {"status": "success", "file_path": file_path}
            if isinstance(result, dict):
                return result
            return {"status": "success", "result": str(result), "file_path": file_path}
        except Exception as e:
            logger.error("文档解析失败: file=%s, error=%s", file_path, str(e))
            raise RuntimeError(f"文档解析失败: {str(e)}") from e

    async def query(
        self,
        tender_id: Optional[int],
        question: str,
        mode: str = "hybrid",
    ) -> str:
        """调用 RAGAnything 进行语义查询。

        Args:
            tender_id: 标书 ID，None 表示查询知识库。
            question: 查询问题。
            mode: 检索模式（hybrid/local/global/naive）。

        Returns:
            RAG 查询结果文本。

        Raises:
            RuntimeError: 查询失败时抛出。
        """
        rag = await self.get_rag_instance(tender_id)
        logger.info(
            "RAG 查询: tender_id=%s, mode=%s, question=%s",
            tender_id,
            mode,
            question[:100],
        )
        try:
            result = await rag.aquery(question, mode=mode)
            if isinstance(result, str):
                return result
            return str(result)
        except Exception as e:
            logger.error("RAG 查询失败: error=%s", str(e))
            raise RuntimeError(f"RAG 查询失败: {str(e)}") from e

    async def rebuild_instance(self) -> None:
        """清除所有缓存的 RAGAnything 实例。

        在 API 配置变更后调用，确保后续请求使用新配置创建实例。
        """
        logger.info("清除 RAG 实例缓存（%d 个实例）", len(self._rag_instances))
        self._rag_instances.clear()
        self._config_snapshot = None


# 全局单例
rag_service = RAGService()
