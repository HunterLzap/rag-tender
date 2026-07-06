"""内置规则库服务。

当前先提供只读目录，用于把系统已经启用的保守规则展示给用户。
后续可在此基础上扩展规则审核、版本、启停和错例反推。
"""

from datetime import datetime
import re
from typing import Any

from app.database import get_db
from app.services.submission_checklist_service import RED_FLAG_RULES


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _builtin_rule_ids() -> set[str]:
    return {str(rule["id"]) for rule in RED_FLAG_RULES}


def _build_rule_catalog(overrides: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    overrides = overrides or {}

    for rule in RED_FLAG_RULES:
        rule_id = str(rule["id"])
        rules.append(
            {
                "id": rule_id,
                "name": rule["name"],
                "domain": "投标待办",
                "rule_type": "red_flag",
                "strictness": "strict",
                "enabled": overrides.get(rule_id, True),
                "keywords": list(rule["keywords"]),
                "description": rule["remark"],
                "source": "内置规则",
                "action": "命中后标记为红线待办，需人工确认完成情况",
            }
        )

    return rules


RULE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "template.tax_social_security_evidence",
        "name": "依法纳税和社保证明核验",
        "category": "资格审查",
        "rule_type": "required_evidence_rule",
        "risk_level": "high",
        "applicable_scene": "招标文件要求投标人依法缴纳税收和社会保障资金。",
        "evidence_requirements": ["纳税证明", "社保证明", "出具主体", "证明期间", "投标人名称一致"],
        "positive_examples": ["同时提供有效纳税证明和社保证明，主体名称与投标人一致。"],
        "negative_examples": ["只有纳税证明但缺少社保证明，或证明期间明显不覆盖招标要求。"],
        "review_notes": "参考模板：发布为正式规则前需确认项目对证明期间、免税或免缴情形的具体口径。",
    },
    {
        "id": "template.similar_performance_contract",
        "name": "类似项目业绩核验",
        "category": "资格审查",
        "rule_type": "tighten_rule",
        "risk_level": "high",
        "applicable_scene": "招标文件要求类似业绩、合同金额、项目数量或验收材料。",
        "evidence_requirements": ["业绩合同", "合同金额", "项目内容", "验收证明", "签订时间"],
        "positive_examples": ["合同内容、金额、时间和验收材料均满足标书明确要求。"],
        "negative_examples": ["仅有项目名称相似，缺少合同金额或验收证明。"],
        "review_notes": "参考模板：需按行业和项目类型细化“类似”的判定边界。",
    },
    {
        "id": "template.personnel_certificate_validity",
        "name": "人员证书有效性核验",
        "category": "资格审查",
        "rule_type": "required_evidence_rule",
        "risk_level": "high",
        "applicable_scene": "招标文件要求项目负责人、技术人员或特种作业人员证书。",
        "evidence_requirements": ["人员证书", "证书等级", "有效期", "人员归属证明", "身份证明"],
        "positive_examples": ["证书等级、专业、有效期和人员归属均能对应标书要求。"],
        "negative_examples": ["证书已过期，或人员证书专业与要求不一致。"],
        "review_notes": "参考模板：人员是否可兼职、社保归属和注册单位需按标书原文复核。",
    },
    {
        "id": "template.financial_statement",
        "name": "财务状况资料核验",
        "category": "资格审查",
        "rule_type": "required_evidence_rule",
        "risk_level": "medium",
        "applicable_scene": "招标文件要求财务报表、审计报告、银行资信或经营状况证明。",
        "evidence_requirements": ["财务报表", "审计报告", "年度范围", "签章", "财务指标"],
        "positive_examples": ["提供标书要求年度的完整财务材料，并有有效签章。"],
        "negative_examples": ["只提供部分年度报表，或缺少审计报告关键页。"],
        "review_notes": "参考模板：财务指标阈值需由项目规则单独配置，不宜模板直接固化。",
    },
    {
        "id": "template.credit_record",
        "name": "信用记录与失信核验",
        "category": "资格审查",
        "rule_type": "exclusion_rule",
        "risk_level": "high",
        "applicable_scene": "招标文件要求未被列入失信、重大税收违法或政府采购严重违法名单。",
        "evidence_requirements": ["信用查询截图", "查询网站", "查询时间", "主体名称", "无失信记录"],
        "positive_examples": ["提供指定平台查询结果，主体一致且查询时间符合要求。"],
        "negative_examples": ["查询主体不一致，或查询时间早于标书允许范围。"],
        "review_notes": "参考模板：排除类规则风险高，正式启用前必须保留人工复核。",
    },
    {
        "id": "template.local_registration_or_filing",
        "name": "备案或本地化要求核验",
        "category": "商务响应",
        "rule_type": "tighten_rule",
        "risk_level": "medium",
        "applicable_scene": "招标文件要求本地备案、分支机构、服务网点或售后响应能力。",
        "evidence_requirements": ["备案证明", "服务网点证明", "地址信息", "授权材料", "响应时限"],
        "positive_examples": ["提供备案或服务网点证明，地址和服务范围满足要求。"],
        "negative_examples": ["仅承诺可提供本地服务，但没有备案或网点证明。"],
        "review_notes": "参考模板：需区分资格门槛和评分项，避免过度收紧。",
    },
    {
        "id": "template.submission_document_completeness",
        "name": "投标文件完整性核验",
        "category": "商务响应",
        "rule_type": "red_flag",
        "risk_level": "high",
        "applicable_scene": "招标文件要求签章、授权书、保证金、正副本、密封或格式文件。",
        "evidence_requirements": ["签章页", "授权书", "保证金凭证", "正副本要求", "格式文件"],
        "positive_examples": ["关键文件齐全，签章和格式与招标要求一致。"],
        "negative_examples": ["缺少法定代表人授权书，或保证金凭证无法对应项目。"],
        "review_notes": "参考模板：适合作为待办红线，不建议自动判定资质不符合。",
    },
    {
        "id": "template.technical_response_deviation",
        "name": "技术响应偏离核验",
        "category": "技术响应",
        "rule_type": "parse_hint_rule",
        "risk_level": "medium",
        "applicable_scene": "招标文件有技术参数、偏离表、响应表或强制技术指标。",
        "evidence_requirements": ["技术响应表", "偏离说明", "参数页", "检测报告", "产品规格"],
        "positive_examples": ["响应表逐项对应技术参数，并提供规格或检测材料支撑。"],
        "negative_examples": ["只写“完全响应”，没有参数页或证明材料支撑关键指标。"],
        "review_notes": "参考模板：优先用于解析提示和待复核，不直接把技术项判定为符合。",
    },
]


def list_rule_templates() -> list[dict[str, Any]]:
    return [dict(template) for template in RULE_TEMPLATES]


def _find_rule_template(template_id: str) -> dict[str, Any] | None:
    clean_template_id = template_id.strip()
    return next((dict(template) for template in RULE_TEMPLATES if template["id"] == clean_template_id), None)


def _rule_draft_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_suggestion_id": row["source_suggestion_id"],
        "name": row["name"],
        "rule_type": row["rule_type"],
        "draft_content": row["draft_content"],
        "draft_status": row["draft_status"],
        "review_reason": row["review_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def create_rule_draft_from_template(
    template_id: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    template = _find_rule_template(template_id)
    clean_reason = reason.strip() if reason else ""
    if template is None or not clean_reason:
        return None

    source_prefix = f"template:{template['id']}:"
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content,
                      draft_status, review_reason, created_at, updated_at
               FROM rule_drafts
               WHERE source_suggestion_id LIKE ? AND draft_status = 'pending_review'
               ORDER BY id DESC
               LIMIT 1""",
            (f"{source_prefix}%",),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            return _rule_draft_from_row(existing)

        now = _now_iso()
        source_suggestion_id = f"{source_prefix}{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        draft_content = (
            f"来源模板：{template['name']}\n"
            f"模板分类：{template['category']}；风险等级：{template['risk_level']}\n"
            f"适用场景：{template['applicable_scene']}\n"
            f"证据要求：{'、'.join(template['evidence_requirements'])}\n"
            f"符合示例：{'；'.join(template['positive_examples'])}\n"
            f"不符合示例：{'；'.join(template['negative_examples'])}\n"
            f"复核说明：{template['review_notes']}\n"
            f"使用原因：{clean_reason}"
        )
        await db.execute(
            """INSERT INTO rule_drafts
               (source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending_review', ?, ?)""",
            (
                source_suggestion_id,
                f"模板草案：{template['name']}",
                template["rule_type"],
                draft_content,
                now,
                now,
            ),
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content,
                      draft_status, review_reason, created_at, updated_at
               FROM rule_drafts
               WHERE source_suggestion_id = ?""",
            (source_suggestion_id,),
        )
        row = await cursor.fetchone()
        return _rule_draft_from_row(row) if row is not None else None
    finally:
        await db.close()


_SIMILARITY_KEYWORDS = (
    "纳税",
    "税收",
    "社保",
    "社会保障",
    "社会保险",
    "保证金",
    "截止",
    "签章",
    "盖章",
    "密封",
    "正本",
    "副本",
    "装订",
    "页码",
    "样品",
    "演示",
    "有效期",
    "范围",
    "等级",
    "人员",
    "业绩",
    "合同金额",
)


def _normalize_rule_text(*parts: str | None) -> str:
    return re.sub(r"\s+", "", "".join(part or "" for part in parts)).lower()


def _rule_similarity_tokens(text: str) -> set[str]:
    normalized = _normalize_rule_text(text)
    tokens = {
        keyword
        for keyword in _SIMILARITY_KEYWORDS
        if keyword.lower() in normalized
    }
    tokens.update(re.findall(r"[A-Za-z0-9]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", normalized))
    for size in (2, 3, 4):
        for index in range(0, max(0, len(chinese) - size + 1)):
            token = chinese[index : index + size]
            if token not in {"规则", "草案", "要求", "证明", "资料", "符合"}:
                tokens.add(token)
    return tokens


def _score_similar_rule(
    target: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[float, list[str]]:
    target_text = _normalize_rule_text(
        target.get("name"),
        target.get("rule_type"),
        target.get("draft_content") or target.get("description"),
    )
    candidate_text = _normalize_rule_text(
        candidate.get("name"),
        candidate.get("rule_type"),
        candidate.get("draft_content") or candidate.get("description"),
        " ".join(candidate.get("keywords") or []),
    )
    target_tokens = _rule_similarity_tokens(target_text)
    candidate_tokens = _rule_similarity_tokens(candidate_text)
    overlap = target_tokens & candidate_tokens
    reasons: list[str] = []
    score = 0.0

    if target.get("rule_type") and target.get("rule_type") == candidate.get("rule_type"):
        score += 0.2
        reasons.append("规则类型相同")

    important_overlap = [
        token
        for token in overlap
        if token in _SIMILARITY_KEYWORDS or len(token) >= 3
    ][:8]
    if important_overlap:
        denominator = max(1, min(len(target_tokens), len(candidate_tokens)))
        score += min(0.75, len(overlap) / denominator)
        reasons.append(f"关键词重合：{'、'.join(important_overlap)}")

    target_name = _normalize_rule_text(target.get("name"))
    candidate_name = _normalize_rule_text(candidate.get("name"))
    if target_name and candidate_name and (target_name in candidate_text or candidate_name in target_text):
        score += 0.25
        reasons.append("名称或标题高度接近")

    return min(score, 1.0), reasons


_LOW_QUALITY_CORRECTION_REASONS = {
    "不对",
    "错误",
    "错了",
    "不符合",
    "需确认",
    "人工确认",
    "不通过",
}

_ACTIONABLE_CORRECTION_KEYWORDS = (
    "没有",
    "缺少",
    "缺失",
    "未找到",
    "未提供",
    "不覆盖",
    "过期",
    "不足",
    "不满足",
    "不符合",
    "不能判定符合",
    "范围",
    "有效期",
    "等级",
    "金额",
    "人员",
    "业绩",
    "社保",
    "纳税",
    "证明",
    "证书",
)

_EVIDENCE_GAP_KEYWORDS = (
    "社保证明",
    "纳税证明",
    "营业执照",
    "认证范围",
    "证书有效期",
    "证书等级",
    "人员证书",
    "业绩合同",
    "合同金额",
    "项目类型",
    "安全生产许可证",
    "资质证书",
)


def _build_rule_suggestion_quality(reason: str) -> dict[str, Any] | None:
    """判断错例原因是否足够生成规则建议，并提取证据缺口。"""
    clean_reason = re.sub(r"\s+", "", reason or "")
    if len(clean_reason) < 6 or clean_reason in _LOW_QUALITY_CORRECTION_REASONS:
        return None

    has_actionable_keyword = any(keyword in clean_reason for keyword in _ACTIONABLE_CORRECTION_KEYWORDS)
    if not has_actionable_keyword:
        return None

    evidence_gaps = [keyword for keyword in _EVIDENCE_GAP_KEYWORDS if keyword in clean_reason]
    if not evidence_gaps:
        if "社保" in clean_reason:
            evidence_gaps.append("社保证明")
        if "纳税" in clean_reason or "税收" in clean_reason:
            evidence_gaps.append("纳税证明")
        if "有效期" in clean_reason:
            evidence_gaps.append("证书有效期")
        if "范围" in clean_reason:
            evidence_gaps.append("认证范围")

    quality_notes = ["原因包含明确证据缺口或可执行收紧条件"]
    if evidence_gaps:
        quality_notes.append(f"识别证据缺口：{'、'.join(dict.fromkeys(evidence_gaps))}")

    return {
        "quality_status": "actionable",
        "quality_notes": "；".join(quality_notes),
        "evidence_gaps": list(dict.fromkeys(evidence_gaps)),
    }


def list_rule_catalog() -> list[dict[str, Any]]:
    """返回默认内置规则目录，不读取数据库覆盖配置。"""
    return _build_rule_catalog()


async def list_rule_catalog_with_overrides() -> list[dict[str, Any]]:
    """返回规则目录，并合并用户启停配置。"""
    overrides = await get_rule_enabled_overrides()
    return _build_rule_catalog(overrides) + await list_custom_rules()


async def get_rule_enabled_overrides() -> dict[str, bool]:
    """读取规则启停覆盖配置。"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT rule_id, enabled FROM rule_overrides")
        rows = await cursor.fetchall()
        return {row["rule_id"]: bool(row["enabled"]) for row in rows}
    finally:
        await db.close()


async def get_enabled_rule_ids() -> set[str]:
    """返回当前启用的内置规则 ID。"""
    overrides = await get_rule_enabled_overrides()
    return {
        rule_id
        for rule_id in _builtin_rule_ids()
        if overrides.get(rule_id, True)
    }


async def _build_rule_reference_lookup() -> dict[str, dict[str, Any]]:
    """构建规则 ID 到展示信息的索引，用于关系追溯展示。"""
    lookup: dict[str, dict[str, Any]] = {}
    for rule in _build_rule_catalog(await get_rule_enabled_overrides()):
        lookup[rule["id"]] = {
            "name": rule["name"],
            "source": "内置规则",
            "status": "enabled" if rule["enabled"] else "disabled",
        }

    db = await get_db()
    try:
        custom_cursor = await db.execute(
            """SELECT id, name, enabled
               FROM custom_rules"""
        )
        custom_rows = await custom_cursor.fetchall()
        for row in custom_rows:
            lookup[row["id"]] = {
                "name": row["name"],
                "source": "已发布自定义规则",
                "status": "enabled" if row["enabled"] else "disabled",
            }

        draft_cursor = await db.execute(
            """SELECT id, name, draft_status
               FROM rule_drafts"""
        )
        draft_rows = await draft_cursor.fetchall()
        for row in draft_rows:
            lookup[f"draft.{row['id']}"] = {
                "name": row["name"],
                "source": "规则草案",
                "status": row["draft_status"],
            }
    finally:
        await db.close()

    return lookup


async def list_rule_relations(rule_id: str) -> list[dict[str, Any]]:
    """返回某条规则的复用/相似关系，用于规则详情追溯。"""
    lookup = await _build_rule_reference_lookup()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_rule_id, target_rule_id, relation_type, reason, created_at
               FROM rule_relations
               WHERE source_rule_id = ? OR target_rule_id = ?
               ORDER BY created_at DESC, id DESC""",
            (rule_id, rule_id),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    relations: list[dict[str, Any]] = []
    for row in rows:
        direction = "outgoing" if row["source_rule_id"] == rule_id else "incoming"
        related_rule_id = row["target_rule_id"] if direction == "outgoing" else row["source_rule_id"]
        related = lookup.get(
            related_rule_id,
            {"name": related_rule_id, "source": "未知来源", "status": "unknown"},
        )
        relations.append(
            {
                "id": row["id"],
                "source_rule_id": row["source_rule_id"],
                "target_rule_id": row["target_rule_id"],
                "relation_type": row["relation_type"],
                "reason": row["reason"],
                "created_at": row["created_at"],
                "direction": direction,
                "related_rule_id": related_rule_id,
                "related_rule_name": related["name"],
                "related_rule_source": related["source"],
                "related_rule_status": related["status"],
            }
        )
    return relations


async def list_rule_versions(rule_id: str) -> list[dict[str, Any]]:
    """返回自定义规则历史版本，按版本号倒序。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, rule_id, version_no, name, rule_type, description,
                      edit_reason, created_at
               FROM rule_versions
               WHERE rule_id = ?
               ORDER BY version_no DESC""",
            (rule_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_custom_rule(
    rule_id: str,
    name: str,
    rule_type: str,
    description: str,
    edit_reason: str | None = None,
) -> dict[str, Any] | None:
    """编辑已发布自定义规则，并把修改前内容保存为历史版本。"""
    clean_rule_id = rule_id.strip()
    clean_name = name.strip()
    clean_rule_type = rule_type.strip()
    clean_description = description.strip()
    clean_edit_reason = edit_reason.strip() if edit_reason else None
    if (
        not clean_rule_id.startswith("custom.")
        or not clean_name
        or not clean_rule_type
        or not clean_description
        or not clean_edit_reason
    ):
        return None

    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, name, rule_type, description
               FROM custom_rules
               WHERE id = ?""",
            (clean_rule_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        version_cursor = await db.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version FROM rule_versions WHERE rule_id = ?",
            (clean_rule_id,),
        )
        version_row = await version_cursor.fetchone()
        next_version = int(version_row["next_version"])
        await db.execute(
            """INSERT INTO rule_versions
               (rule_id, version_no, name, rule_type, description, edit_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                clean_rule_id,
                next_version,
                row["name"],
                row["rule_type"],
                row["description"],
                clean_edit_reason,
                now,
            ),
        )
        await db.execute(
            """UPDATE custom_rules
               SET name = ?, rule_type = ?, description = ?, updated_at = ?
               WHERE id = ?""",
            (clean_name, clean_rule_type, clean_description, now, clean_rule_id),
        )
        await db.commit()
    finally:
        await db.close()

    rules = await list_rule_catalog_with_overrides()
    return next(rule for rule in rules if rule["id"] == clean_rule_id)


async def rollback_custom_rule(
    rule_id: str,
    version_no: int,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """将自定义规则回滚到指定历史版本，并保存回滚前内容。"""
    clean_rule_id = rule_id.strip()
    clean_reason = reason.strip() if reason else None
    if not clean_rule_id.startswith("custom.") or version_no <= 0 or not clean_reason:
        return None

    now = _now_iso()
    db = await get_db()
    try:
        current_cursor = await db.execute(
            """SELECT id, name, rule_type, description
               FROM custom_rules
               WHERE id = ?""",
            (clean_rule_id,),
        )
        current_row = await current_cursor.fetchone()
        if current_row is None:
            return None

        target_cursor = await db.execute(
            """SELECT name, rule_type, description
               FROM rule_versions
               WHERE rule_id = ? AND version_no = ?""",
            (clean_rule_id, version_no),
        )
        target_row = await target_cursor.fetchone()
        if target_row is None:
            return None

        version_cursor = await db.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version FROM rule_versions WHERE rule_id = ?",
            (clean_rule_id,),
        )
        version_row = await version_cursor.fetchone()
        next_version = int(version_row["next_version"])
        await db.execute(
            """INSERT INTO rule_versions
               (rule_id, version_no, name, rule_type, description, edit_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                clean_rule_id,
                next_version,
                current_row["name"],
                current_row["rule_type"],
                current_row["description"],
                f"回滚到 v{version_no}：{clean_reason}",
                now,
            ),
        )
        await db.execute(
            """UPDATE custom_rules
               SET name = ?, rule_type = ?, description = ?, updated_at = ?
               WHERE id = ?""",
            (
                target_row["name"],
                target_row["rule_type"],
                target_row["description"],
                now,
                clean_rule_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    rules = await list_rule_catalog_with_overrides()
    return next(rule for rule in rules if rule["id"] == clean_rule_id)


async def merge_custom_rule(
    source_rule_id: str,
    target_rule_id: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """将重复自定义规则归并到目标规则，并停用源规则。"""
    clean_source_rule_id = source_rule_id.strip()
    clean_target_rule_id = target_rule_id.strip()
    if (
        not clean_source_rule_id.startswith("custom.")
        or not clean_target_rule_id
        or clean_source_rule_id == clean_target_rule_id
    ):
        return None

    now = _now_iso()
    clean_reason = reason.strip() if reason and reason.strip() else "重复规则归并到主规则维护"
    db = await get_db()
    try:
        source_cursor = await db.execute(
            "SELECT id, enabled FROM custom_rules WHERE id = ?",
            (clean_source_rule_id,),
        )
        source_row = await source_cursor.fetchone()
        if source_row is None:
            return None

        target_exists = False
        if clean_target_rule_id in _builtin_rule_ids():
            target_exists = True
        elif clean_target_rule_id.startswith("custom."):
            target_cursor = await db.execute(
                "SELECT id FROM custom_rules WHERE id = ?",
                (clean_target_rule_id,),
            )
            target_exists = await target_cursor.fetchone() is not None

        if not target_exists:
            return None

        previous_enabled = bool(source_row["enabled"])
        await db.execute(
            """INSERT INTO rule_relations
               (source_rule_id, target_rule_id, relation_type, reason, created_at)
               VALUES (?, ?, 'merged_into', ?, ?)""",
            (clean_source_rule_id, clean_target_rule_id, clean_reason, now),
        )
        await db.execute(
            "UPDATE custom_rules SET enabled = 0, updated_at = ? WHERE id = ?",
            (now, clean_source_rule_id),
        )
        if previous_enabled:
            await db.execute(
                """INSERT INTO rule_change_logs
                   (rule_id, previous_enabled, new_enabled, reason, created_at)
                   VALUES (?, 1, 0, ?, ?)""",
                (
                    clean_source_rule_id,
                    f"归并到 {clean_target_rule_id}。{clean_reason}",
                    now,
                ),
            )
        await db.commit()
    finally:
        await db.close()

    return {
        "source_rule_id": clean_source_rule_id,
        "target_rule_id": clean_target_rule_id,
        "relation_type": "merged_into",
        "reason": clean_reason,
        "created_at": now,
    }


async def update_rule_enabled(
    rule_id: str,
    enabled: bool,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """更新单条规则启停状态。"""
    if rule_id.startswith("custom."):
        return await _update_custom_rule_enabled(rule_id, enabled, reason)

    if rule_id not in _builtin_rule_ids():
        return None

    overrides = await get_rule_enabled_overrides()
    previous_enabled = overrides.get(rule_id, True)
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO rule_overrides (rule_id, enabled, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(rule_id) DO UPDATE SET
                 enabled = excluded.enabled,
                 updated_at = excluded.updated_at""",
            (rule_id, 1 if enabled else 0, now),
        )
        if previous_enabled != enabled:
            await db.execute(
                """INSERT INTO rule_change_logs
                   (rule_id, previous_enabled, new_enabled, reason, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    rule_id,
                    1 if previous_enabled else 0,
                    1 if enabled else 0,
                    reason,
                    now,
                ),
            )
        await db.commit()
    finally:
        await db.close()

    rules = await list_rule_catalog_with_overrides()
    return next(rule for rule in rules if rule["id"] == rule_id)


async def _update_custom_rule_enabled(
    rule_id: str,
    enabled: bool,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """更新自定义规则启停状态。"""
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT enabled FROM custom_rules WHERE id = ?",
            (rule_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        previous_enabled = bool(row["enabled"])
        await db.execute(
            "UPDATE custom_rules SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now, rule_id),
        )
        if previous_enabled != enabled:
            await db.execute(
                """INSERT INTO rule_change_logs
                   (rule_id, previous_enabled, new_enabled, reason, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    rule_id,
                    1 if previous_enabled else 0,
                    1 if enabled else 0,
                    reason,
                    now,
                ),
            )
        await db.commit()
    finally:
        await db.close()

    rules = await list_rule_catalog_with_overrides()
    return next(rule for rule in rules if rule["id"] == rule_id)


async def list_rule_change_logs(limit: int = 100) -> list[dict[str, Any]]:
    """按时间倒序返回规则启停变更记录。"""
    safe_limit = max(1, min(limit, 500))
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, rule_id, previous_enabled, new_enabled, reason, created_at
               FROM rule_change_logs
               ORDER BY id DESC
               LIMIT ?""",
            (safe_limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "rule_id": row["rule_id"],
                "previous_enabled": bool(row["previous_enabled"]),
                "new_enabled": bool(row["new_enabled"]),
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        await db.close()


async def list_rule_suggestions(limit: int = 100) -> list[dict[str, Any]]:
    """从人工错例中生成规则候选建议。

    第一版只处理高风险误判：系统原判 matched，人工改为 unmatched。
    这类错例说明当前规则过松，应该建议收紧。
    """
    safe_limit = max(1, min(limit, 500))
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT
                   mc.id,
                   mc.match_id,
                   mc.tender_id,
                   mc.requirement_id,
                   mc.previous_status,
                   mc.confirmed_status,
                   mc.correction_reason,
                   mc.evidence_snapshot,
                   mc.created_at,
                   tr.title AS requirement_title,
                   tr.content AS requirement_content,
                   tr.category AS requirement_category,
                   t.title AS tender_title,
                   t.filename AS tender_filename
               FROM match_corrections mc
               LEFT JOIN tender_requirements tr ON tr.id = mc.requirement_id
               LEFT JOIN tenders t ON t.id = mc.tender_id
               WHERE mc.previous_status = 'matched'
                 AND mc.confirmed_status = 'unmatched'
               ORDER BY mc.id DESC
               LIMIT ?""",
            (safe_limit,),
        )
        rows = await cursor.fetchall()
        review_cursor = await db.execute(
            "SELECT suggestion_id, review_status, review_reason FROM rule_suggestion_reviews"
        )
        review_rows = await review_cursor.fetchall()
        reviews = {
            row["suggestion_id"]: {
                "review_status": row["review_status"],
                "review_reason": row["review_reason"],
            }
            for row in review_rows
        }

        suggestions: list[dict[str, Any]] = []
        for row in rows:
            suggestion_id = f"correction-{row['id']}"
            review = reviews.get(
                suggestion_id,
                {"review_status": "pending", "review_reason": None},
            )
            requirement_title = row["requirement_title"] or "未命名要求"
            reason = row["correction_reason"] or "人工将系统符合修正为不符合，建议补充更严格核验规则"
            quality = _build_rule_suggestion_quality(reason)
            if quality is None:
                continue
            suggestions.append(
                {
                    "id": suggestion_id,
                    "source": "match_correction",
                    "source_id": row["id"],
                    "suggestion_type": "tighten_rule",
                    "title": f"收紧规则：{requirement_title}",
                    "reason": reason,
                    "confidence": 0.85,
                    "quality_status": quality["quality_status"],
                    "quality_notes": quality["quality_notes"],
                    "evidence_gaps": quality["evidence_gaps"],
                    "requirement_id": row["requirement_id"],
                    "requirement_title": requirement_title,
                    "requirement_content": row["requirement_content"],
                    "requirement_category": row["requirement_category"],
                    "tender_id": row["tender_id"],
                    "tender_title": row["tender_title"],
                    "tender_filename": row["tender_filename"],
                    "evidence_snapshot": row["evidence_snapshot"],
                    "review_status": review["review_status"],
                    "review_reason": review["review_reason"],
                    "created_at": row["created_at"],
                }
            )
        return suggestions
    finally:
        await db.close()


async def review_rule_suggestion(
    suggestion_id: str,
    review_status: str,
    review_reason: str | None = None,
) -> dict[str, Any] | None:
    """处理规则建议，记录采纳或忽略原因。"""
    if review_status not in {"pending", "accepted", "rejected"}:
        return None

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO rule_suggestion_reviews
               (suggestion_id, review_status, review_reason, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(suggestion_id) DO UPDATE SET
                 review_status = excluded.review_status,
                 review_reason = excluded.review_reason,
                 updated_at = excluded.updated_at""",
            (suggestion_id, review_status, review_reason, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    if review_status == "accepted":
        await _upsert_rule_draft_from_suggestion(suggestion_id)

    return {
        "suggestion_id": suggestion_id,
        "review_status": review_status,
        "review_reason": review_reason,
    }


async def _upsert_rule_draft_from_suggestion(suggestion_id: str) -> None:
    suggestions = await list_rule_suggestions(limit=500)
    suggestion = next((item for item in suggestions if item["id"] == suggestion_id), None)
    if suggestion is None:
        return

    name = f"规则草案：{suggestion['requirement_title']}"
    draft_content = (
        f"来源错例：{suggestion['reason']}\n"
        f"建议方向：系统曾判定符合，人工修正为不符合；后续应增加更严格证据核验。\n"
        f"招标要求：{suggestion.get('requirement_content') or suggestion['requirement_title']}"
    )
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO rule_drafts
               (source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending_review', ?, ?)
               ON CONFLICT(source_suggestion_id) DO UPDATE SET
                 name = excluded.name,
                 rule_type = excluded.rule_type,
                 draft_content = excluded.draft_content,
                 draft_status = 'pending_review',
                 updated_at = excluded.updated_at""",
            (
                suggestion_id,
                name,
                suggestion["suggestion_type"],
                draft_content,
                now,
                now,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def list_rule_drafts(limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content,
                      draft_status, review_reason, created_at, updated_at
               FROM rule_drafts
               ORDER BY id DESC
               LIMIT ?""",
            (safe_limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "source_suggestion_id": row["source_suggestion_id"],
                "name": row["name"],
                "rule_type": row["rule_type"],
                "draft_content": row["draft_content"],
                "draft_status": row["draft_status"],
                "review_reason": row["review_reason"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    finally:
        await db.close()


async def update_rule_draft(
    draft_id: int,
    name: str,
    rule_type: str,
    draft_content: str,
    edit_reason: str | None = None,
) -> dict[str, Any] | None:
    """编辑待审核规则草案。已发布/已驳回草案不允许直接修改。"""
    clean_name = name.strip()
    clean_rule_type = rule_type.strip()
    clean_content = draft_content.strip()
    if not clean_name or not clean_rule_type or not clean_content:
        return None

    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, draft_status
               FROM rule_drafts
               WHERE id = ?""",
            (draft_id,),
        )
        row = await cursor.fetchone()
        if row is None or row["draft_status"] != "pending_review":
            return None

        await db.execute(
            """UPDATE rule_drafts
               SET name = ?, rule_type = ?, draft_content = ?,
                   review_reason = ?, updated_at = ?
               WHERE id = ?""",
            (
                clean_name,
                clean_rule_type,
                clean_content,
                edit_reason.strip() if edit_reason else None,
                now,
                draft_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    drafts = await list_rule_drafts(limit=500)
    return next((draft for draft in drafts if draft["id"] == draft_id), None)


async def list_similar_rules_for_draft(
    draft_id: int,
    limit: int = 10,
) -> list[dict[str, Any]] | None:
    """返回某条草案发布前可能重复/相似的规则候选。"""
    safe_limit = max(1, min(limit, 50))
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content,
                      draft_status, review_reason, created_at, updated_at
               FROM rule_drafts
               WHERE id = ?""",
            (draft_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        target = dict(row)

        custom_cursor = await db.execute(
            """SELECT id, source_draft_id, name, rule_type, description,
                      enabled, created_at, updated_at
               FROM custom_rules
               ORDER BY created_at DESC"""
        )
        custom_rows = await custom_cursor.fetchall()

        draft_cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content,
                      draft_status, review_reason, created_at, updated_at
               FROM rule_drafts
               WHERE id != ?
               ORDER BY updated_at DESC""",
            (draft_id,),
        )
        other_drafts = await draft_cursor.fetchall()
    finally:
        await db.close()

    candidates: list[dict[str, Any]] = []
    for rule in _build_rule_catalog(await get_rule_enabled_overrides()):
        candidates.append(
            {
                "rule_id": rule["id"],
                "name": rule["name"],
                "rule_type": rule["rule_type"],
                "source": "内置规则",
                "status": "enabled" if rule["enabled"] else "disabled",
                "description": rule["description"],
                "keywords": rule["keywords"],
            }
        )

    for row in custom_rows:
        if row["source_draft_id"] == draft_id:
            continue
        candidates.append(
            {
                "rule_id": row["id"],
                "name": row["name"],
                "rule_type": row["rule_type"],
                "source": "已发布自定义规则",
                "status": "enabled" if row["enabled"] else "disabled",
                "description": row["description"],
                "keywords": [],
            }
        )

    for row in other_drafts:
        candidates.append(
            {
                "rule_id": f"draft.{row['id']}",
                "name": row["name"],
                "rule_type": row["rule_type"],
                "source": "规则草案",
                "status": row["draft_status"],
                "draft_content": row["draft_content"],
                "description": row["draft_content"],
                "keywords": [],
            }
        )

    similar: list[dict[str, Any]] = []
    for candidate in candidates:
        similarity, reasons = _score_similar_rule(target, candidate)
        if similarity < 0.2 or not reasons:
            continue
        similar.append(
            {
                "rule_id": candidate["rule_id"],
                "name": candidate["name"],
                "rule_type": candidate["rule_type"],
                "source": candidate["source"],
                "status": candidate["status"],
                "similarity": round(similarity, 3),
                "reasons": reasons,
                "description": candidate.get("description") or "",
            }
        )

    similar.sort(key=lambda item: item["similarity"], reverse=True)
    return similar[:safe_limit]


async def reuse_existing_rule_for_draft(
    draft_id: int,
    target_rule_id: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """将待审核草案标记为复用已有规则，避免重复发布。"""
    clean_target_rule_id = target_rule_id.strip()
    if not clean_target_rule_id:
        return None

    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, draft_status FROM rule_drafts WHERE id = ?",
            (draft_id,),
        )
        draft_row = await cursor.fetchone()
        if draft_row is None or draft_row["draft_status"] != "pending_review":
            return None

        target_exists = False
        if clean_target_rule_id in _builtin_rule_ids():
            target_exists = True
        elif clean_target_rule_id.startswith("custom."):
            target_cursor = await db.execute(
                "SELECT id FROM custom_rules WHERE id = ?",
                (clean_target_rule_id,),
            )
            target_exists = await target_cursor.fetchone() is not None
        elif clean_target_rule_id.startswith("draft."):
            try:
                target_draft_id = int(clean_target_rule_id.split(".", 1)[1])
            except (IndexError, ValueError):
                target_draft_id = -1
            target_cursor = await db.execute(
                "SELECT id FROM rule_drafts WHERE id = ?",
                (target_draft_id,),
            )
            target_exists = await target_cursor.fetchone() is not None

        if not target_exists:
            return None

        source_rule_id = f"draft.{draft_id}"
        clean_reason = reason.strip() if reason else "复用已有规则，避免重复发布"
        await db.execute(
            """INSERT INTO rule_relations
               (source_rule_id, target_rule_id, relation_type, reason, created_at)
               VALUES (?, ?, 'duplicate_of', ?, ?)""",
            (source_rule_id, clean_target_rule_id, clean_reason, now),
        )
        await db.execute(
            """UPDATE rule_drafts
               SET draft_status = 'rejected', review_reason = ?, updated_at = ?
               WHERE id = ?""",
            (f"复用已有规则：{clean_target_rule_id}。{clean_reason}", now, draft_id),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "draft_id": draft_id,
        "source_rule_id": f"draft.{draft_id}",
        "target_rule_id": clean_target_rule_id,
        "relation_type": "duplicate_of",
        "reason": reason,
    }


async def review_rule_draft(
    draft_id: int,
    draft_status: str,
    review_reason: str | None = None,
    similar_rule_ids: list[str] | None = None,
    difference_reason: str | None = None,
) -> dict[str, Any] | None:
    """审核规则草案，发布后生成自定义规则。"""
    if draft_status not in {"pending_review", "published", "rejected"}:
        return None
    clean_similar_rule_ids = [
        rule_id.strip()
        for rule_id in (similar_rule_ids or [])
        if rule_id and rule_id.strip()
    ]
    clean_difference_reason = difference_reason.strip() if difference_reason else None
    if draft_status == "published" and clean_similar_rule_ids and not clean_difference_reason:
        return None

    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_suggestion_id, name, rule_type, draft_content
               FROM rule_drafts
               WHERE id = ?""",
            (draft_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        await db.execute(
            """UPDATE rule_drafts
               SET draft_status = ?, review_reason = ?, updated_at = ?
               WHERE id = ?""",
            (draft_status, review_reason, now, draft_id),
        )

        if draft_status == "published":
            custom_rule_id = f"custom.rule_draft.{draft_id}"
            await db.execute(
                """INSERT INTO custom_rules
                   (id, source_draft_id, name, rule_type, description,
                    enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name = excluded.name,
                     rule_type = excluded.rule_type,
                     description = excluded.description,
                     enabled = 1,
                     updated_at = excluded.updated_at""",
                (
                    custom_rule_id,
                    draft_id,
                    row["name"],
                    row["rule_type"],
                    row["draft_content"],
                    now,
                    now,
                ),
            )
            for target_rule_id in clean_similar_rule_ids:
                await db.execute(
                    """INSERT INTO rule_relations
                       (source_rule_id, target_rule_id, relation_type, reason, created_at)
                       VALUES (?, ?, 'similar_to', ?, ?)""",
                    (
                        custom_rule_id,
                        target_rule_id,
                        clean_difference_reason,
                        now,
                    ),
                )
        await db.commit()
    finally:
        await db.close()

    drafts = await list_rule_drafts(limit=500)
    return next((draft for draft in drafts if draft["id"] == draft_id), None)


async def list_custom_rules() -> list[dict[str, Any]]:
    """返回已发布的自定义规则，用于规则库展示。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, source_draft_id, name, rule_type, description,
                      enabled, created_at, updated_at
               FROM custom_rules
               ORDER BY created_at DESC"""
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "domain": "自定义规则",
                "rule_type": row["rule_type"],
                "strictness": "strict",
                "enabled": bool(row["enabled"]),
                "keywords": [],
                "description": row["description"],
                "source": "规则草案",
                "action": "已发布为自定义规则，后续可接入匹配/红线执行链路",
            }
            for row in rows
        ]
    finally:
        await db.close()
