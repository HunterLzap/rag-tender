import json
import logging
import time
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ModelCall, ModelConfig
from app.security import decrypt_secret
from app.services.jobs import check_canceled

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class ModelGatewayError(RuntimeError):
    pass


class LiveModelCallsDisabled(ModelGatewayError):
    pass


class ModelOutputTruncated(ModelGatewayError):
    pass


@dataclass(frozen=True)
class ActiveModel:
    config: ModelConfig
    api_key: str


async def get_active_model(session: AsyncSession, config_id: str | None = None) -> ActiveModel:
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    if config_id:
        stmt = select(ModelConfig).where(ModelConfig.id == config_id)
    else:
        stmt = stmt.order_by(ModelConfig.updated_at.desc())
    config = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if config is None:
        raise ModelGatewayError("尚未配置可用的大模型")
    return ActiveModel(config=config, api_key=decrypt_secret(config.api_key_encrypted))


async def complete_text(
    session: AsyncSession,
    *,
    system: str,
    user: str,
    purpose: str,
    job_id: str | None = None,
    prompt_version: str = "v2.0",
    config_id: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    if not get_settings().live_model_calls:
        raise LiveModelCallsDisabled(
            "真实模型调用已禁用；请使用模拟模型，或显式设置 TENDER_LIVE_MODEL_CALLS=true"
        )
    await check_canceled(session, job_id)
    active = await get_active_model(session, config_id)
    settings = get_settings()
    started = time.monotonic()
    payload = {
        "model": active.config.text_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            response = await client.post(
                f"{active.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {active.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        finish_reason = body["choices"][0].get("finish_reason")
        usage = body.get("usage") or {}
    except Exception as exc:
        await _record_model_call(
            session,
            job_id=job_id,
            purpose=purpose,
            provider=active.config.provider,
            model=active.config.text_model,
            prompt_version=prompt_version,
            latency_ms=int((time.monotonic() - started) * 1000),
            success=False,
            error=f"{type(exc).__name__}: {exc}"[:2000],
        )
        raise ModelGatewayError(f"模型调用失败: {exc}") from exc

    truncated = finish_reason == "length"
    error = (
        f"模型输出达到长度上限 {max_tokens}，结构化内容不完整" if truncated else None
    )
    await _record_model_call(
        session,
        job_id=job_id,
        purpose=purpose,
        provider=active.config.provider,
        model=active.config.text_model,
        prompt_version=prompt_version,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        latency_ms=int((time.monotonic() - started) * 1000),
        success=not truncated,
        error=error,
    )
    if truncated:
        raise ModelOutputTruncated(error)
    return content


async def _record_model_call(
    session: AsyncSession,
    *,
    job_id: str | None,
    purpose: str,
    provider: str,
    model: str,
    prompt_version: str,
    latency_ms: int,
    success: bool,
    error: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    session.add(
        ModelCall(
            job_id=job_id,
            purpose=purpose,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
    )
    await session.commit()


async def structured_text(
    session: AsyncSession,
    *,
    system: str,
    user: str,
    output_model: type[T],
    purpose: str,
    job_id: str | None = None,
    prompt_version: str = "v2.0",
    config_id: str | None = None,
    max_tokens: int = 8192,
) -> T:
    schema = json.dumps(output_model.model_json_schema(), ensure_ascii=False)
    instruction = (
        "只输出合法 JSON，不要 Markdown 代码围栏或解释。"
        f"必须符合以下 JSON Schema：\n{schema}"
    )
    content = await complete_text(
        session,
        system=f"{system}\n\n{instruction}",
        user=user,
        purpose=purpose,
        job_id=job_id,
        prompt_version=prompt_version,
        config_id=config_id,
        max_tokens=max_tokens,
    )
    try:
        return output_model.model_validate_json(_strip_fences(content))
    except (ValidationError, ValueError) as exc:
        raise ModelGatewayError(f"模型结构化输出校验失败: {exc}") from exc


def _strip_fences(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


async def test_model(
    *, base_url: str, api_key: str, model: str, timeout_seconds: int = 30
) -> tuple[bool, int, str]:
    if not get_settings().live_model_calls:
        return False, 0, "真实模型调用已禁用；设置 TENDER_LIVE_MODEL_CALLS=true 后才能测试连接"
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "回复 OK"}],
                    "max_tokens": 8,
                },
            )
            response.raise_for_status()
        return True, int((time.monotonic() - started) * 1000), "连接成功"
    except Exception as exc:
        return False, int((time.monotonic() - started) * 1000), str(exc)[:500]
