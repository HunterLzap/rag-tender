from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ModelCall, ModelConfig
from app.security import decrypt_secret
from app.services.jobs import check_canceled
from app.services.model_gateway import (
    LiveModelCallsDisabled,
    ModelGatewayError,
    ModelOutputTruncated,
)


async def transcribe_scanned_page(
    session: AsyncSession,
    image_path: Path,
    *,
    job_id: str | None = None,
) -> str:
    if not get_settings().live_model_calls:
        raise LiveModelCallsDisabled("真实模型调用已禁用；扫描页保留为待人工复核")
    await check_canceled(session, job_id)
    config = (
        await session.execute(
            select(ModelConfig)
            .where(ModelConfig.is_active.is_(True), ModelConfig.vision_model.is_not(None))
            .order_by(ModelConfig.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if config is None:
        raise ModelGatewayError("扫描页需要视觉模型，但尚未配置 vision_model")
    import base64

    data = base64.b64encode(image_path.read_bytes()).decode()
    payload: dict[str, Any] = {
        "model": config.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请逐行提取这张招标文件扫描页中的文字。保持表格行结构。"
                            "不要总结，不要补充不存在的内容。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{data}"},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 8192,
    }
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {decrypt_secret(config.api_key_encrypted)}"
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        if body["choices"][0].get("finish_reason") == "length":
            raise ModelOutputTruncated("扫描页转写输出超限，需人工复核")
        if not content or not content.strip():
            raise ModelGatewayError("扫描页未识别出文字，需人工复核")
        session.add(
            ModelCall(
                job_id=job_id,
                purpose="vision_transcription",
                provider=config.provider,
                model=config.vision_model or "",
                success=True,
            )
        )
        await session.commit()
        return content
    except Exception as exc:
        session.add(
            ModelCall(
                job_id=job_id,
                purpose="vision_transcription",
                provider=config.provider,
                model=config.vision_model or "",
                success=False,
                error=str(exc)[:2000],
            )
        )
        await session.commit()
        if isinstance(exc, ModelGatewayError):
            raise
        raise ModelGatewayError(f"扫描页转写失败: {exc}") from exc
