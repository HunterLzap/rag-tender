"""投标待办清单业务逻辑。

从 submission 类标书要求派生待办清单记录，管理三档状态
（未开始 / 进行中 / 已完成）。支持手动新增不在标书中的待办项。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from app.database import get_db
from app.models.checklist import SubmissionChecklist

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


RED_FLAG_RULES = [
    {
        "id": "submission.red_flag.deposit",
        "name": "投标保证金红线",
        "keywords": ("投标保证金", "保证金", "缴纳", "逾期", "无效投标", "不予受理"),
        "remark": "保证金：金额、缴纳方式、到账/提交截止时间错误可能导致废标",
    },
    {
        "id": "submission.red_flag.deadline",
        "name": "提交截止时间红线",
        "keywords": ("截止时间", "递交截止", "提交截止", "逾期", "不予受理", "无效投标"),
        "remark": "截止时间：投标文件、保证金或响应材料逾期可能导致无效投标",
    },
    {
        "id": "submission.red_flag.signature_seal",
        "name": "签章密封红线",
        "keywords": ("签字", "签章", "盖章", "电子签章", "密封", "封装"),
        "remark": "签章/密封：漏签、漏章、密封不符合要求可能导致废标",
    },
    {
        "id": "submission.red_flag.format_copies",
        "name": "正副本与装订红线",
        "keywords": ("正本", "副本", "份数", "目录", "页码", "装订"),
        "remark": "格式/份数：正副本、格式、装订或页码不符合要求可能影响响应有效性",
    },
    {
        "id": "submission.red_flag.sample_demo",
        "name": "样品演示红线",
        "keywords": ("样品", "演示", "现场踏勘", "述标", "答辩"),
        "remark": "样品/演示：漏交样品、未参加演示/踏勘/答辩可能影响评审",
    },
    {
        "id": "submission.red_flag.authorization",
        "name": "授权书红线",
        "keywords": ("授权委托书", "法定代表人授权", "法人授权", "被授权人", "身份证"),
        "remark": "授权书：法定代表人授权书、身份证明或被授权人信息缺失可能导致投标无效",
    },
    {
        "id": "submission.red_flag.validity_period",
        "name": "投标有效期红线",
        "keywords": ("投标有效期", "有效期不少于", "有效期不得少于", "响应有效期"),
        "remark": "投标有效期：有效期短于招标要求可能导致投标无效",
    },
    {
        "id": "submission.red_flag.price_ceiling",
        "name": "报价上限红线",
        "keywords": ("最高限价", "控制价", "预算价", "预算金额", "报价不得超过", "投标报价不得超过"),
        "remark": "报价上限：报价超过预算、最高限价或控制价可能导致投标无效",
    },
    {
        "id": "submission.red_flag.blind_bid_sensitive",
        "name": "暗标敏感信息红线",
        "keywords": ("暗标", "不得出现投标人名称", "公司名称", "联系人", "联系电话", "电话", "地址", "可识别信息"),
        "remark": "暗标：出现公司名、联系人、电话、地址等敏感信息可能导致废标",
    },
    {
        "id": "submission.red_flag.electronic_submission",
        "name": "电子投标提交红线",
        "keywords": ("电子投标", "上传截止", "CA签章", "CA 签章", "文件命名", "投标文件格式"),
        "remark": "电子投标：文件命名、格式、上传截止时间或 CA 签章错误可能导致提交失败",
    },
]

_GENERATED_RED_FLAG_REMARKS = {str(rule["remark"]) for rule in RED_FLAG_RULES}


async def _get_enabled_red_flag_rule_ids() -> set[str]:
    """读取当前启用的红线规则 ID。"""
    all_rule_ids = {str(rule["id"]) for rule in RED_FLAG_RULES}
    db = await get_db()
    try:
        cursor = await db.execute("SELECT rule_id, enabled FROM rule_overrides")
        rows = await cursor.fetchall()
        overrides = {row["rule_id"]: bool(row["enabled"]) for row in rows}
        return {
            rule_id
            for rule_id in all_rule_ids
            if overrides.get(rule_id, True)
        }
    finally:
        await db.close()


def _detect_red_flag_remark(
    title: str | None,
    content: str | None,
    enabled_rule_ids: set[str] | None = None,
) -> Optional[str]:
    """识别投标提交类要求里的常见废标红线。"""
    text = f"{title or ''}\n{content or ''}"
    matched: list[str] = []
    for rule in RED_FLAG_RULES:
        if enabled_rule_ids is not None and str(rule["id"]) not in enabled_rule_ids:
            continue
        keywords = tuple(rule["keywords"])
        remark = str(rule["remark"])
        if any(keyword in text for keyword in keywords):
            matched.append(remark)

    if not matched:
        return None

    unique_matched = list(dict.fromkeys(matched))
    return "【红线】" + "；".join(unique_matched)


def _merge_remark(existing: str | None, addition: str | None) -> str | None:
    """保留人工备注，并幂等追加系统识别的风险提示。"""
    if not addition:
        return existing
    if existing and addition in existing:
        return existing
    return f"{existing}；{addition}" if existing else addition


def _strip_generated_red_flag_remarks(remark: str | None) -> str | None:
    """移除系统按旧规则生成的红线段，保留人工备注。"""
    if not remark:
        return remark

    kept_segments: list[str] = []
    for segment in remark.split("；"):
        clean_segment = segment.removeprefix("【红线】")
        if clean_segment in _GENERATED_RED_FLAG_REMARKS:
            continue
        kept_segments.append(segment)

    return "；".join(kept_segments) or None


async def _backfill_red_flag_remarks(tender_id: int) -> None:
    """为已存在的待办清单补充红线提示，兼容旧数据。"""
    enabled_rule_ids = await _get_enabled_red_flag_rule_ids()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, item_name, description, remark
               FROM submission_checklist
               WHERE tender_id = ?
               ORDER BY id""",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        now = _now_iso()
        changed = False
        for row in rows:
            current_remark = row["remark"]
            base_remark = _strip_generated_red_flag_remarks(current_remark)
            red_flag_remark = _detect_red_flag_remark(
                row["item_name"],
                row["description"],
                enabled_rule_ids,
            )
            next_remark = _merge_remark(base_remark, red_flag_remark)
            if next_remark != current_remark:
                await db.execute(
                    """UPDATE submission_checklist
                       SET remark = ?, updated_at = ?
                       WHERE id = ?""",
                    (next_remark, now, row["id"]),
                )
                changed = True
        if changed:
            await db.commit()
    finally:
        await db.close()


# 允许的状态值
_VALID_STATUSES = {"not_started", "in_progress", "done"}


async def init_from_requirements(tender_id: int) -> list[SubmissionChecklist]:
    """从 submission 类标书要求派生待办清单记录。

    筛选 requirement_nature='submission' 或 category='submission' 的要求，
    为每条创建一条 SubmissionChecklist 记录。如果已有记录则跳过（幂等）。

    Args:
        tender_id: 标书 ID。

    Returns:
        新创建的 SubmissionChecklist 列表。
    """
    db = await get_db()
    try:
        # 检查是否已有记录
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM submission_checklist WHERE tender_id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            return []

        # 查询 submission 类要求（requirement_nature='submission' 或 category='submission'）
        cursor = await db.execute(
            """SELECT * FROM tender_requirements
               WHERE tender_id = ?
                 AND (requirement_nature = 'submission' OR category = 'submission')
               ORDER BY id""",
            (tender_id,),
        )
        req_rows = await cursor.fetchall()

        if not req_rows:
            logger.info("标书 %s 无 submission 类要求，待办清单为空", tender_id)
            return []

        now = _now_iso()
        created: list[SubmissionChecklist] = []
        enabled_rule_ids = await _get_enabled_red_flag_rule_ids()
        for req in req_rows:
            req_dict = dict(req)
            item_name = req_dict.get("title") or req_dict.get("content") or ""
            description = req_dict.get("content") or None
            remark = None
            # 灰色地带备注提示
            if description and "【灰色地带】" in description:
                remark = "灰色地带：请人工确认分类是否正确"
            remark = _merge_remark(
                remark,
                _detect_red_flag_remark(item_name, description, enabled_rule_ids),
            )

            cursor = await db.execute(
                """INSERT INTO submission_checklist
                   (tender_id, requirement_id, item_name, description,
                    status, remark, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'not_started', ?, ?, ?)""",
                (tender_id, req_dict["id"], item_name, description,
                 remark, now, now),
            )
            new_id = cursor.lastrowid
            created.append(SubmissionChecklist(
                id=new_id,
                tender_id=tender_id,
                requirement_id=req_dict["id"],
                item_name=item_name,
                description=description,
                status="not_started",
                remark=remark,
                created_at=now,
                updated_at=now,
            ))

        await db.commit()
        logger.info("待办清单初始化: tender_id=%s, 创建 %d 条记录", tender_id, len(created))
        return created
    finally:
        await db.close()


async def get_all(tender_id: int) -> list[SubmissionChecklist]:
    """获取标书的待办清单。

    首次访问时自动从 submission 类要求初始化。

    Args:
        tender_id: 标书 ID。

    Returns:
        SubmissionChecklist 列表。
    """
    # 先检查是否已有记录
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM submission_checklist WHERE tender_id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        count = row["cnt"] if row else 0
    finally:
        await db.close()

    # 首次访问，自动初始化
    if count == 0:
        await init_from_requirements(tender_id)
    else:
        await _backfill_red_flag_remarks(tender_id)

    # 返回所有记录
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM submission_checklist WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        return [SubmissionChecklist(**dict(r)) for r in rows]
    finally:
        await db.close()


async def update(item_id: int, data: Any) -> Optional[SubmissionChecklist]:
    """更新单条待办清单项。

    Args:
        item_id: 待办清单记录 ID。
        data: 包含 status / remark / item_name / description 的更新数据。

    Returns:
        更新后的 SubmissionChecklist，不存在时返回 None。
    """
    allowed_fields = {"status", "remark", "item_name", "description"}
    values = data.model_dump(exclude_unset=True)
    updates = {key: value for key, value in values.items() if key in allowed_fields}

    # 校验 status 值
    if "status" in updates and updates["status"] not in _VALID_STATUSES:
        return None

    if not updates:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM submission_checklist WHERE id = ?",
                (item_id,),
            )
            row = await cursor.fetchone()
            return SubmissionChecklist(**dict(row)) if row else None
        finally:
            await db.close()

    now = _now_iso()
    db = await get_db()
    try:
        sets_parts = [f"{field} = ?" for field in updates]
        sets_parts.append("updated_at = ?")
        params = list(updates.values()) + [now, item_id]
        await db.execute(
            f"UPDATE submission_checklist SET {', '.join(sets_parts)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM submission_checklist WHERE id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
        return SubmissionChecklist(**dict(row)) if row else None
    finally:
        await db.close()


async def add_manual_item(tender_id: int, data: Any) -> SubmissionChecklist:
    """手动新增待办项。

    Args:
        tender_id: 标书 ID。
        data: 包含 item_name / description / remark 的创建数据。

    Returns:
        新创建的 SubmissionChecklist。
    """
    values = data.model_dump(exclude_unset=True)
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO submission_checklist
               (tender_id, requirement_id, item_name, description,
                status, remark, created_at, updated_at)
               VALUES (?, NULL, ?, ?, 'not_started', ?, ?, ?)""",
            (tender_id,
             values.get("item_name", ""),
             values.get("description"),
             values.get("remark"),
             now, now),
        )
        await db.commit()
        new_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT * FROM submission_checklist WHERE id = ?",
            (new_id,),
        )
        row = await cursor.fetchone()
        return SubmissionChecklist(**dict(row))
    finally:
        await db.close()
