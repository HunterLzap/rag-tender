"""技术响应表业务逻辑。

从 product_spec 类标书要求派生技术响应记录，管理"标书要求值 vs 实际值"对比。
用户手动填写 actual_value，支持单条和批量更新。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from app.database import get_db
from app.models.technical import TechnicalResponse

logger = logging.getLogger(__name__)

# required_value 摘要截断长度
_MAX_CONTENT_LEN = 80


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _derive_required_value(req: dict[str, Any]) -> str:
    """从标书要求派生 required_value。

    优先取 numeric_value + numeric_operator + numeric_unit 拼接（如 ">=32GB"），
    无数值则取 content 摘要（截断至 80 字符）。

    Args:
        req: 标书要求字典。

    Returns:
        派生的 required_value 字符串。
    """
    numeric_value = req.get("numeric_value")
    numeric_operator = req.get("numeric_operator") or ""
    numeric_unit = req.get("numeric_unit") or ""

    if numeric_value:
        return f"{numeric_operator}{numeric_value}{numeric_unit}".strip()

    content = req.get("content") or req.get("title") or ""
    if len(content) > _MAX_CONTENT_LEN:
        return content[:_MAX_CONTENT_LEN] + "…"
    return content


async def init_from_requirements(tender_id: int) -> list[TechnicalResponse]:
    """从 product_spec 类标书要求派生技术响应记录。

    筛选 category='product_spec' 的要求，为每条创建一条 TechnicalResponse 记录。
    如果已有记录则跳过（幂等）。

    Args:
        tender_id: 标书 ID。

    Returns:
        新创建的 TechnicalResponse 列表。
    """
    db = await get_db()
    try:
        # 检查是否已有记录
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM technical_responses WHERE tender_id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            # 已有记录，不再初始化
            return []

        # 查询 product_spec 类要求
        cursor = await db.execute(
            "SELECT * FROM tender_requirements WHERE tender_id = ? AND category = 'product_spec' ORDER BY id",
            (tender_id,),
        )
        req_rows = await cursor.fetchall()

        if not req_rows:
            logger.info("标书 %s 无 product_spec 类要求，技术响应表为空", tender_id)
            return []

        now = _now_iso()
        created: list[TechnicalResponse] = []
        for req in req_rows:
            req_dict = dict(req)
            spec_name = req_dict.get("title") or req_dict.get("content") or ""
            required_value = _derive_required_value(req_dict)
            is_hard = bool(req_dict.get("is_hard", 1))

            cursor = await db.execute(
                """INSERT INTO technical_responses
                   (tender_id, requirement_id, spec_name, required_value,
                    actual_value, response_status, is_hard, remark, created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL, 'pending', ?, NULL, ?, ?)""",
                (tender_id, req_dict["id"], spec_name, required_value,
                 1 if is_hard else 0, now, now),
            )
            new_id = cursor.lastrowid
            created.append(TechnicalResponse(
                id=new_id,
                tender_id=tender_id,
                requirement_id=req_dict["id"],
                spec_name=spec_name,
                required_value=required_value,
                actual_value=None,
                response_status="pending",
                is_hard=is_hard,
                remark=None,
                created_at=now,
                updated_at=now,
            ))

        await db.commit()
        logger.info("技术响应表初始化: tender_id=%s, 创建 %d 条记录", tender_id, len(created))
        return created
    finally:
        await db.close()


async def get_all(tender_id: int) -> list[TechnicalResponse]:
    """获取标书的技术响应列表。

    首次访问时自动从 product_spec 类要求初始化。

    Args:
        tender_id: 标书 ID。

    Returns:
        TechnicalResponse 列表。
    """
    # 先检查是否已有记录
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM technical_responses WHERE tender_id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        count = row["cnt"] if row else 0
    finally:
        await db.close()

    # 首次访问，自动初始化
    if count == 0:
        await init_from_requirements(tender_id)

    # 返回所有记录
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM technical_responses WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        return [TechnicalResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


async def update(response_id: int, data: Any) -> Optional[TechnicalResponse]:
    """更新单条技术响应。

    Args:
        response_id: 技术响应记录 ID。
        data: 包含 actual_value / remark / is_hard 的更新数据。

    Returns:
        更新后的 TechnicalResponse，不存在时返回 None。
    """
    allowed_fields = {"actual_value", "response_status", "remark", "is_hard"}
    values = data.model_dump(exclude_unset=True)
    updates = {key: value for key, value in values.items() if key in allowed_fields}

    if not updates:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM technical_responses WHERE id = ?",
                (response_id,),
            )
            row = await cursor.fetchone()
            return TechnicalResponse(**dict(row)) if row else None
        finally:
            await db.close()

    now = _now_iso()
    db = await get_db()
    try:
        sets_parts = [f"{field} = ?" for field in updates]
        sets_parts.append("updated_at = ?")
        params = list(updates.values()) + [now, response_id]
        await db.execute(
            f"UPDATE technical_responses SET {', '.join(sets_parts)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM technical_responses WHERE id = ?",
            (response_id,),
        )
        row = await cursor.fetchone()
        return TechnicalResponse(**dict(row)) if row else None
    finally:
        await db.close()


async def batch_update(tender_id: int, items: list[dict[str, Any]]) -> list[TechnicalResponse]:
    """批量更新技术响应。

    Args:
        tender_id: 标书 ID（用于验证归属）。
        items: 要更新的项目列表，每项包含 id + actual_value/remark。

    Returns:
        更新后的 TechnicalResponse 列表。
    """
    now = _now_iso()
    db = await get_db()
    try:
        updated_ids: list[int] = []
        for item in items:
            item_id = item.get("id")
            if item_id is None:
                continue
            sets_parts = ["updated_at = ?"]
            params: list[Any] = [now]
            for field in ("actual_value", "response_status", "remark"):
                if field in item:
                    sets_parts.insert(0, f"{field} = ?")
                    params.insert(0, item[field])
            params.append(item_id)
            params.append(tender_id)
            await db.execute(
                f"UPDATE technical_responses SET {', '.join(sets_parts)} WHERE id = ? AND tender_id = ?",
                params,
            )
            updated_ids.append(item_id)
        await db.commit()

        if not updated_ids:
            return []
        placeholders = ",".join("?" for _ in updated_ids)
        cursor = await db.execute(
            f"SELECT * FROM technical_responses WHERE id IN ({placeholders}) ORDER BY id",
            updated_ids,
        )
        rows = await cursor.fetchall()
        return [TechnicalResponse(**dict(r)) for r in rows]
    finally:
        await db.close()
