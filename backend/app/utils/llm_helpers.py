"""LLM / Embedding / Vision 函数工厂。

从 DB 中的 API 配置动态构建 RAG-Anything 所需的异步函数。
T02 阶段提供工厂函数签名和占位实现，T03 由 RAGService 调用。
"""

import logging
import hashlib
import time
from datetime import datetime
from typing import Any, Callable, Optional

import httpx

from app.database import get_db
from app.models.config_model import ApiConfig
from app.utils.mask import mask_in_log

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _api_key_fingerprint(api_key: str | None) -> str | None:
    if not api_key:
        return None
    clean = api_key.strip()
    if not clean:
        return None
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12]


async def _record_llm_call(
    *,
    task_type: str,
    config_type: str,
    api_config: ApiConfig,
    success: bool,
    duration_ms: int,
    prompt_chars: int = 0,
    response_chars: int = 0,
    error_message: str | None = None,
) -> None:
    """记录模型调用元数据，不记录明文 API Key。"""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO llm_call_logs
               (task_type, config_type, provider, model_name, base_url, success,
                duration_ms, prompt_chars, response_chars, error_message,
                api_key_fingerprint, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_type,
                config_type,
                api_config.provider,
                api_config.model_name,
                api_config.base_url,
                int(success),
                max(0, duration_ms),
                max(0, prompt_chars),
                max(0, response_chars),
                error_message[:500] if error_message else None,
                _api_key_fingerprint(api_config.api_key),
                _now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def _openai_chat_request(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """发送 OpenAI 兼容的 chat/completions 请求。

    Args:
        base_url: API 基础 URL。
        api_key: API 密钥。
        model: 模型名称。
        messages: 消息列表。
        **kwargs: 额外请求参数（如 max_tokens、temperature）。

    Returns:
        API 响应 JSON。

    Raises:
        Exception: 请求失败时抛出。
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        **kwargs,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def _openai_embedding_request(
    base_url: str,
    api_key: str,
    model: str,
    input_text: str,
) -> dict[str, Any]:
    """发送 OpenAI 兼容的 embeddings 请求。

    Args:
        base_url: API 基础 URL。
        api_key: API 密钥。
        model: 模型名称。
        input_text: 待嵌入的文本。

    Returns:
        API 响应 JSON。

    Raises:
        Exception: 请求失败时抛出。
    """
    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": input_text,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def build_llm_func(api_config: ApiConfig) -> Callable:
    """构建 LLM 异步函数。

    返回一个 ``async def(prompt: str, **kwargs) -> str`` 函数，
    内部调用 OpenAI 兼容的 chat/completions 接口。

    Args:
        api_config: LLM API 配置。

    Returns:
        异步函数，接受 prompt 返回 LLM 响应文本。
    """

    async def llm_func(prompt: str, **kwargs: Any) -> str:
        """调用 LLM 生成回复。

        Args:
            prompt: 用户提示词。
            **kwargs: 额外参数（system_prompt、temperature 等）。

        Returns:
            LLM 生成的文本。
        """
        system_prompt = kwargs.pop("system_prompt", "You are a helpful assistant.")
        task_type = kwargs.pop("task_type", "llm")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        logger.info(
            "LLM 调用: model=%s, key=%s",
            api_config.model_name,
            mask_in_log(api_config.api_key),
        )
        start = time.perf_counter()
        try:
            result = await _openai_chat_request(
                base_url=api_config.base_url or "",
                api_key=api_config.api_key or "",
                model=api_config.model_name or "",
                messages=messages,
                **kwargs,
            )
            content = result["choices"][0]["message"]["content"]
            await _record_llm_call(
                task_type=task_type,
                config_type="llm",
                api_config=api_config,
                success=True,
                duration_ms=int((time.perf_counter() - start) * 1000),
                prompt_chars=len(prompt) + len(system_prompt),
                response_chars=len(content or ""),
            )
            return content
        except Exception as e:
            await _record_llm_call(
                task_type=task_type,
                config_type="llm",
                api_config=api_config,
                success=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                prompt_chars=len(prompt) + len(system_prompt),
                error_message=str(e),
            )
            raise

    return llm_func


def build_embedding_func(api_config: ApiConfig) -> Callable:
    """构建 Embedding 异步函数。

    返回一个 ``async def(text: str) -> list[float]`` 函数，
    内部调用 OpenAI 兼容的 embeddings 接口。

    Args:
        api_config: Embedding API 配置。

    Returns:
        异步函数，接受文本返回嵌入向量。
    """

    async def embedding_func(text: str) -> list[float]:
        """调用 Embedding API 生成文本向量。

        Args:
            text: 待嵌入的文本。

        Returns:
            浮点数向量列表。
        """
        logger.info(
            "Embedding 调用: model=%s, key=%s",
            api_config.model_name,
            mask_in_log(api_config.api_key),
        )
        result = await _openai_embedding_request(
            base_url=api_config.base_url or "",
            api_key=api_config.api_key or "",
            model=api_config.model_name or "",
            input_text=text,
        )
        return result["data"][0]["embedding"]

    return embedding_func


def build_vision_func(api_config: ApiConfig) -> Callable:
    """构建 Vision 异步函数。

    返回一个 ``async def(image_base64: str, prompt: str) -> str`` 函数，
    内部调用 OpenAI 兼容的 chat/completions 接口（多模态）。

    Args:
        api_config: Vision API 配置。

    Returns:
        异步函数，接受 base64 图片和提示词返回识别结果文本。
    """

    async def vision_func(image_base64: str, prompt: str = "请识别图片中的文字信息") -> str:
        """调用 Vision API 识别图片内容。

        Args:
            image_base64: base64 编码的图片数据。
            prompt: 提示词。

        Returns:
            Vision API 返回的识别结果文本。
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            }
        ]
        logger.info(
            "Vision 调用: model=%s, key=%s",
            api_config.model_name,
            mask_in_log(api_config.api_key),
        )
        result = await _openai_chat_request(
            base_url=api_config.base_url or "",
            api_key=api_config.api_key or "",
            model=api_config.model_name or "",
            messages=messages,
            max_tokens=1000,
        )
        return result["choices"][0]["message"]["content"]

    return vision_func
