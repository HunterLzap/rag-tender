from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ModelCall, ModelConfig
from app.security import decrypt_secret


async def transcribe_scanned_page(
    session: AsyncSession,
    image_path: Path,
    *,
    job_id: str | None = None,
) -> str:
    config = (
        await session.execute(
            select(ModelConfig)
            .where(ModelConfig.is_active.is_(True), ModelConfig.vision_model.is_not(None))
            .order_by(ModelConfig.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if config is None:
        raise RuntimeError("扫描页需要视觉模型，但尚未配置 vision_model")
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
        raise
