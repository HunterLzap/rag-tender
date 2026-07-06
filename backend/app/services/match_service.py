"""匹配引擎：语义匹配 + 规则校验（P0-07 + P0-08）。

对标书要求与知识库资质进行双重匹配：
1. 语义匹配：用 RAG 向量检索知识库中相关资质
2. 规则校验：5 类数值规则（注册资本/合同金额/营业收入/资产负债率/人员年限）
3. 生成 MatchResult：含不符合点、期望资质、知识库是否已有该资质
"""

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Optional

from app.database import get_db
from app.models.match import MatchEvidenceItem, MatchResult
from app.models.tender import TenderRequirement
from app.services.rag_service import get_llm_func

logger = logging.getLogger(__name__)

_MATCH_PROGRESS: dict[int, dict[str, Any]] = {}


def _set_match_progress(tender_id: int, **updates: Any) -> None:
    """Update in-memory matching progress for frontend polling."""
    current = _MATCH_PROGRESS.get(tender_id, {})
    current.update(updates)
    current["tender_id"] = tender_id
    current["updated_at"] = _now_iso()
    _MATCH_PROGRESS[tender_id] = current


def start_match_progress(tender_id: int) -> None:
    """Mark a tender match task as queued."""
    _MATCH_PROGRESS[tender_id] = {
        "tender_id": tender_id,
        "status": "queued",
        "stage": "queued",
        "current": 0,
        "total": 0,
        "matched": 0,
        "unmatched": 0,
        "needs_review": 0,
        "message": "匹配任务已提交，等待后端开始处理",
        "current_requirement": None,
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "finished_at": None,
        "error": None,
    }


def get_match_progress(tender_id: int) -> dict[str, Any]:
    """Return current matching progress."""
    return _MATCH_PROGRESS.get(
        tender_id,
        {
            "tender_id": tender_id,
            "status": "idle",
            "stage": "idle",
            "current": 0,
            "total": 0,
            "matched": 0,
            "unmatched": 0,
            "needs_review": 0,
            "message": "当前没有正在运行的匹配任务",
            "current_requirement": None,
            "started_at": None,
            "updated_at": None,
            "finished_at": None,
            "error": None,
        },
    )

# ---------------------------------------------------------------------------
# 5 类数值规则模式
# ---------------------------------------------------------------------------

RULE_PATTERNS: dict[str, str] = {
    "registered_capital": r"注册资本[≥>=\u2265]+(\d+(?:\.\d+)?)\s*[万万]?元",
    "contract_amount": r"合同金额[≥>=\u2265]+(\d+(?:\.\d+)?)\s*[万万]?元",
    "revenue": r"营业收入[≥>=\u2265]+(\d+(?:\.\d+)?)\s*[万万]?元",
    "debt_ratio": r"资产负债率[≤<=\u2264]+(\d+(?:\.\d+)?)\s*%",
    "personnel_years": r"(\d+)\s*年以上",
}

# 运算符模式（用于提取 >=、<=、>、<、≥、≤）
_OPERATOR_PATTERN = r"[≥>=\u2265\u2264]+"

# 资质名称 → 规则类型映射（用于从资质信息中提取对应数值）
QUAL_RULE_MAP: dict[str, list[str]] = {
    "registered_capital": ["注册资本", "资金"],
    "contract_amount": ["合同金额", "业绩", "合同"],
    "revenue": ["营业收入", "营收"],
    "debt_ratio": ["资产负债率", "负债率"],
    "personnel_years": ["从业年限", "工作经验", "年限"],
}

_MATCH_SYNONYMS: dict[str, list[str]] = {
    "低压电工作业": ["低压电工", "低压电工作业证", "低压电工作业操作证"],
    "电工作业": ["电工证", "电工操作证", "特种作业证"],
    "身份证明": ["身份证", "身份证复印件", "居民身份证"],
    "社保证明": ["社保", "社会保险", "参保证明", "养老保险"],
    "职称": ["工程师", "助理工程师", "资格证明", "资格证书"],
    "毕业证书": ["学历", "毕业证", "专业学习"],
    "管理体系认证": [
        "质量管理体系认证",
        "环境管理体系认证",
        "职业健康安全管理体系认证",
        "ISO9001",
        "ISO14001",
        "ISO45001",
        "体系认证证书",
    ],
    "纳税证明": ["依法缴纳税收", "缴纳税收", "纳税", "完税证明", "税收完税证明"],
    "财务会计报告": ["健全的财务会计制度", "财务会计制度", "财务报表", "财务报告"],
}


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _tokenize_match_text(text: str) -> set[str]:
    """抽取用于资质匹配的中文/英文/数字关键词。"""
    if not text:
        return set()
    tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text))
    for canonical, aliases in _MATCH_SYNONYMS.items():
        if canonical in text or any(alias in text for alias in aliases):
            tokens.add(canonical)
            tokens.update(aliases)
    return tokens


def _score_qualification_match(
    query_text: str,
    query_tokens: set[str],
    qualification_text: str,
) -> float:
    """计算要求文本和资质文本的轻量匹配分。"""
    if not query_text or not qualification_text:
        return 0.0
    score = 0.0
    normalized_qual = re.sub(r"\s+", "", qualification_text)
    normalized_query = re.sub(r"\s+", "", query_text)

    for canonical, aliases in _MATCH_SYNONYMS.items():
        qual_hit = canonical in normalized_qual or any(alias in normalized_qual for alias in aliases)
        query_hit = canonical in normalized_query or any(alias in normalized_query for alias in aliases)
        if qual_hit and query_hit:
            score += 0.65

    if query_tokens:
        matched_tokens = {
            token for token in query_tokens
            if len(token) >= 2 and token in normalized_qual
        }
        score += min(0.4, len(matched_tokens) * 0.12)

    return min(score, 1.0)


_MATCHABLE_REQUIREMENT_CATEGORIES = {"qualification", "performance", "financial", "personnel"}

_NON_EVIDENCE_REQUIREMENT_KEYWORDS = (
    "独立承担民事责任",
    "履行合同所必需",
    "履行合同设备",
    "专业技术能力",
    "无重大违法",
    "重大违法记录",
    "法律、行政法规",
    "法律行政法规",
    "其他条件",
    "失信被执行人",
    "信用中国",
    "政府采购严重失信",
    "非公益",
    "公益一类事业单位",
    "关联关系",
    "单位负责人为同一人",
    "控股、管理关系",
    "不可兼任",
    "不得兼任",
    "本项目的特定资格要求",
    "投标报价",
    "最高限价",
    "财政预算",
    "违约赔偿",
    "预算金额",
)


def _is_non_evidence_requirement(req: TenderRequirement) -> bool:
    """判断是否属于不能由资质库文件直接证明的声明/承诺/规则类要求。"""
    text = f"{req.title or ''}\n{req.content or ''}\n{req.raw_text or ''}"
    return any(keyword in text for keyword in _NON_EVIDENCE_REQUIREMENT_KEYWORDS)


def _should_match(req: TenderRequirement) -> bool:
    """判断该要求是否需要走知识库匹配流程。

    分流规则：
    - category=product_spec → 直接返回 False，走技术响应表，不参与匹配
    - requirement_nature=submission → 直接返回 False，走待办清单，不参与匹配
    - category 只允许 qualification/performance/financial/personnel
    - 声明/承诺/信用查询/报价规则类要求不进入资质库匹配

    Args:
        req: 标书要求。

    Returns:
        True 表示需要匹配，False 表示跳过。
    """
    if req.category == "product_spec":
        return False
    if req.requirement_nature == "submission":
        return False
    if req.category not in _MATCHABLE_REQUIREMENT_CATEGORIES:
        return False
    if _is_non_evidence_requirement(req):
        return False
    return True


def _parse_numeric_from_requirement(content: str) -> Optional[dict[str, Any]]:
    """从标书要求文本中解析数值规则。

    检查 5 类规则模式，如果匹配则返回规则类型、数值、运算符、单位。

    Args:
        content: 标书要求描述文本。

    Returns:
        包含 rule_type/value/operator/unit 的字典，无匹配时返回 None。
    """
    if not content:
        return None

    for rule_type, pattern in RULE_PATTERNS.items():
        match = re.search(pattern, content)
        if match:
            value_str = match.group(1)
            try:
                value = float(value_str)
            except ValueError:
                continue

            # 提取运算符
            op_match = re.search(_OPERATOR_PATTERN, content)
            operator = op_match.group(0) if op_match else ">="

            # 提取单位
            if rule_type == "debt_ratio":
                unit = "%"
            elif "万元" in content or "万" in content:
                unit = "万元"
            elif "元" in content:
                unit = "元"
            else:
                unit = ""

            return {
                "rule_type": rule_type,
                "value": value,
                "operator": operator,
                "unit": unit,
            }

    return None


def _parse_numeric_from_qualification(
    qual_name: str, qual_scope: str, rule_type: str
) -> Optional[float]:
    """从资质信息中解析对应数值。

    Args:
        qual_name: 资质名称。
        qual_scope: 认证范围。
        rule_type: 规则类型。

    Returns:
        解析出的数值，未找到时返回 None。
    """
    search_text = f"{qual_name or ''} {qual_scope or ''}"

    keywords = QUAL_RULE_MAP.get(rule_type, [])
    for keyword in keywords:
        # 查找关键词附近的数值
        pattern = rf"{keyword}.*?(\d+(?:\.\d+)?)\s*[万万]?元?"
        match = re.search(pattern, search_text)
        if match:
            try:
                value = float(match.group(1))
                # 如果原文有"万"，转换为万元单位
                if "万" in search_text:
                    return value
                return value
            except ValueError:
                continue

    return None


def _check_numeric_rule(
    req_numeric: dict[str, Any], qual_value: Optional[float]
) -> tuple[bool, str]:
    """校验数值规则是否满足。

    Args:
        req_numeric: 标书要求的数值规则。
        qual_value: 资质的实际数值。

    Returns:
        (是否满足, 不满足时的详情描述)。
    """
    if qual_value is None:
        return False, f"知识库中未找到对应的数值信息"

    req_value = req_numeric["value"]
    operator = req_numeric["operator"]
    unit = req_numeric["unit"]

    # 统一运算符
    op = operator.replace("≥", ">=").replace("≤", "<=")

    if op == ">=":
        satisfied = qual_value >= req_value
    elif op == "<=":
        satisfied = qual_value <= req_value
    elif op == ">":
        satisfied = qual_value > req_value
    elif op == "<":
        satisfied = qual_value < req_value
    else:
        satisfied = qual_value >= req_value

    if not satisfied:
        detail = f"实际值 {qual_value}{unit} {op} 要求 {req_value}{unit}（不满足）"
    else:
        detail = f"实际值 {qual_value}{unit} {op} 要求 {req_value}{unit}（满足）"

    return satisfied, detail


def _evidence_item(
    check_key: str,
    label: str,
    expected_value: str | None,
    actual_value: str | None,
    status: str,
    reason: str,
    critical: bool = True,
) -> MatchEvidenceItem:
    """Create one field-level evidence check item."""
    return MatchEvidenceItem(
        check_key=check_key,
        label=label,
        expected_value=expected_value,
        actual_value=actual_value,
        status=status,
        reason=reason,
        critical=critical,
    )


def _text_contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _parse_date_text(value: str | None) -> Optional[date]:
    """Parse common certificate date formats."""
    if not value:
        return None
    match = re.search(r"(\d{4})[-年./](\d{1,2})[-月./](\d{1,2})", value)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _has_meaningful_overlap(requirement_text: str, actual_text: str | None) -> bool:
    """Return true when the actual field contains at least one requirement token."""
    if not actual_text:
        return False
    actual_normalized = re.sub(r"\s+", "", actual_text)
    tokens = {
        token
        for token in _tokenize_match_text(requirement_text)
        if token not in {"投标人", "投标单位", "供应商", "有效期", "相关服务", "覆盖"}
    }
    return any(token in actual_normalized for token in tokens)


def _verify_qualification_evidence(
    requirement: TenderRequirement,
    qualification: dict[str, Any],
    similarity: float,
) -> tuple[str, str, Optional[str], list[MatchEvidenceItem]]:
    """Conservatively verify a qualification candidate with field-level evidence.

    Similarity only selects a candidate. Final automatic matched status requires
    all critical evidence checks to pass. Missing critical evidence stays
    needs_review instead of being promoted to matched.
    """
    req_text = requirement.content or requirement.title or requirement.raw_text or ""
    qual_name = str(qualification.get("name") or "")
    qual_scope = str(qualification.get("scope") or "")
    qual_holder = str(qualification.get("holder") or "")
    qual_level = str(qualification.get("level") or "")
    qual_expiry = str(qualification.get("expiry_date") or "")
    qual_status = str(qualification.get("status") or "")
    qual_text = f"{qual_name} {qual_scope} {qual_holder}"
    evidence_items: list[MatchEvidenceItem] = []

    cert_type_status = "pass" if similarity >= 0.7 else "unknown"
    evidence_items.append(
        _evidence_item(
            "certificate_type",
            "证书类型",
            requirement.title or req_text,
            qual_name,
            cert_type_status,
            "候选资质字段与要求高相似" if cert_type_status == "pass" else "仅找到候选资质，证书类型需人工确认",
        )
    )

    if requirement.category == "personnel":
        evidence_items.append(
            _evidence_item(
                "holder",
                "持证人员",
                "拟派人员持证",
                qual_holder or None,
                "pass" if qual_holder else "unknown",
                "已识别持证人员" if qual_holder else "未识别持证人员，需人工确认",
            )
        )
    elif _text_contains_any(req_text, ("投标人", "投标单位", "供应商", "单位", "企业")):
        evidence_items.append(
            _evidence_item(
                "holder",
                "持证主体",
                "投标主体",
                qual_holder or None,
                "pass" if qual_holder else "unknown",
                "已识别持证主体" if qual_holder else "未识别持证主体，需人工确认",
            )
        )

    if _text_contains_any(req_text, ("有效", "有效期", "投标截止", "开标")):
        expiry_date = _parse_date_text(qual_expiry)
        if qual_status == "expired":
            expiry_status = "fail"
            expiry_reason = "资质状态为已过期"
        elif expiry_date is None:
            expiry_status = "unknown"
            expiry_reason = "未识别有效期，不能自动判定投标截止日是否有效"
        elif expiry_date < date.today():
            expiry_status = "fail"
            expiry_reason = f"有效期 {qual_expiry} 早于当前日期"
        else:
            expiry_status = "pass"
            expiry_reason = "已识别有效期且未过期"
        evidence_items.append(
            _evidence_item(
                "expiry_date",
                "有效期",
                "投标截止日有效",
                qual_expiry or None,
                expiry_status,
                expiry_reason,
            )
        )

    if _text_contains_any(req_text, ("范围", "覆盖", "专业", "服务", "经营范围")):
        if not qual_scope:
            scope_status = "unknown"
            scope_reason = "未识别证书范围，需人工确认是否覆盖要求"
        elif _has_meaningful_overlap(req_text, qual_scope):
            scope_status = "pass"
            scope_reason = "证书范围与要求存在字段重合"
        else:
            scope_status = "unknown"
            scope_reason = "已识别证书范围，但未能自动确认覆盖要求"
        evidence_items.append(
            _evidence_item(
                "scope",
                "适用范围",
                req_text,
                qual_scope or None,
                scope_status,
                scope_reason,
            )
        )

    if _text_contains_any(req_text, ("等级", "一级", "二级", "三级", "甲级", "乙级", "丙级")):
        evidence_items.append(
            _evidence_item(
                "level",
                "等级",
                "满足要求等级",
                qual_level or None,
                "pass" if qual_level and qual_level in req_text else "unknown",
                "已识别等级字段" if qual_level else "未识别等级字段，需人工确认",
            )
        )

    if _text_contains_any(req_text, ("纳税", "税收", "完税")) and _text_contains_any(
        req_text, ("社保", "社会保障", "社会保险")
    ):
        has_tax = _text_contains_any(qual_text, ("纳税", "税收", "完税"))
        has_social_security = _text_contains_any(qual_text, ("社保", "社会保障", "社会保险"))
        evidence_items.append(
            _evidence_item(
                "tax_payment",
                "纳税证明",
                "依法缴纳税收",
                qual_name if has_tax else None,
                "pass" if has_tax else "unknown",
                "已识别纳税证明" if has_tax else "未识别纳税证明",
            )
        )
        evidence_items.append(
            _evidence_item(
                "social_security",
                "社保证明",
                "依法缴纳社会保障资金",
                qual_name if has_social_security else None,
                "pass" if has_social_security else "unknown",
                "已识别社保证明" if has_social_security else "未识别社保证明，不能仅凭纳税证明自动通过",
            )
        )

    critical_items = [item for item in evidence_items if item.critical]
    failed = [item for item in critical_items if item.status == "fail"]
    unknown = [item for item in critical_items if item.status == "unknown"]

    if failed:
        status = "unmatched"
        reason = "字段级证据核验不通过"
        mismatch_detail = (
            f"① 不符合点: {'；'.join(item.reason or item.label for item in failed)}\n"
            f"② 期望资质: {req_text}\n"
            f"③ 知识库检查: 已找到候选资质，但关键字段不满足"
        )
    elif unknown:
        status = "needs_review"
        reason = "字段级证据不完整，需人工确认"
        mismatch_detail = (
            f"① 需人工确认: {'；'.join(item.reason or item.label for item in unknown)}\n"
            f"② 期望资质: {req_text}\n"
            f"③ 知识库检查: 已找到候选资质，但证据链不完整"
        )
    else:
        status = "matched"
        reason = "字段级证据核验通过"
        mismatch_detail = None

    return status, reason, mismatch_detail, evidence_items


def _custom_rule_keyword(name: str) -> str:
    """Extract the concrete requirement phrase from a custom rule name."""
    keyword = re.sub(r"\s+", "", name or "")
    keyword = re.sub(r"^(规则草案[:：]?|自定义[:：]?)", "", keyword)
    keyword = re.sub(r"(复核规则|收紧规则|匹配规则|判定规则|规则|要求)$", "", keyword)
    return keyword


def _custom_tighten_rule_hits_requirement(
    requirement: TenderRequirement,
    rule: dict[str, Any],
) -> bool:
    """Return true when a published tighten rule is clearly about this requirement."""
    req_text = re.sub(
        r"\s+",
        "",
        f"{requirement.title or ''}{requirement.content or ''}{requirement.raw_text or ''}",
    )
    if not req_text:
        return False

    name = str(rule.get("name") or "")
    description = str(rule.get("description") or "")
    rule_text = re.sub(r"\s+", "", f"{name}{description}")
    keyword = _custom_rule_keyword(name)

    if len(keyword) >= 4 and keyword in req_text:
        return True
    if len(req_text) >= 8 and req_text in rule_text:
        return True

    ignored_tokens = {
        "规则",
        "复核",
        "收紧",
        "人工",
        "确认",
        "要求",
        "投标人",
        "投标单位",
        "供应商",
    }
    req_tokens = _tokenize_match_text(req_text)
    rule_tokens = _tokenize_match_text(rule_text)
    meaningful_hits = [
        token
        for token in req_tokens & rule_tokens
        if len(token) >= 4 and token not in ignored_tokens
    ]
    return bool(meaningful_hits)


def _apply_custom_tighten_rules(
    requirement: TenderRequirement,
    status: str,
    reason: Optional[str],
    mismatch_detail: Optional[str],
    expected_qualification: Optional[str],
    evidence_items: list[MatchEvidenceItem],
    custom_tighten_rules: list[dict[str, Any]],
) -> tuple[str, Optional[str], Optional[str], Optional[str], list[MatchEvidenceItem]]:
    """Downgrade automatic matches to manual review when custom tighten rules hit."""
    if status != "matched":
        return status, reason, mismatch_detail, expected_qualification, evidence_items

    hit_rule = next(
        (
            rule
            for rule in custom_tighten_rules
            if _custom_tighten_rule_hits_requirement(requirement, rule)
        ),
        None,
    )
    if hit_rule is None:
        return status, reason, mismatch_detail, expected_qualification, evidence_items

    req_text = requirement.content or requirement.title or requirement.raw_text or ""
    rule_name = str(hit_rule.get("name") or hit_rule.get("id") or "未命名规则")
    rule_id = str(hit_rule.get("id") or rule_name)
    new_items = list(evidence_items)
    new_items.append(
        _evidence_item(
            f"custom_rule:{rule_id}",
            "自定义收紧规则",
            req_text or None,
            rule_name,
            "unknown",
            "命中已发布自定义收紧规则，自动通过结果需人工复核",
        )
    )

    new_reason = f"{reason or '匹配通过'}；命中自定义收紧规则「{rule_name}」，需人工复核"
    new_detail = mismatch_detail or (
        f"① 需人工确认: 命中已发布自定义收紧规则「{rule_name}」，不能直接自动通过\n"
        f"② 期望资质: {req_text}\n"
        "③ 知识库检查: 已上传相关文件，但需按自定义规则复核"
    )
    return "needs_review", new_reason, new_detail, expected_qualification or req_text, new_items


def _parse_amount_to_wan(value: str | None) -> Optional[float]:
    """把合同金额文本转换为万元数值。"""
    if not value:
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万元|万|W|w|元)?", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or "万"
    if unit == "元":
        return amount / 10000
    return amount


def _extract_required_contract_amount(content: str) -> Optional[float]:
    """从业绩要求中提取合同金额下限（万元）。"""
    if not content:
        return None
    patterns = (
        r"合同金额(?:不低于|不少于|达到|≥|>=|大于等于)?\s*(\d+(?:\.\d+)?)\s*(万元|万|元)?",
        r"金额(?:不低于|不少于|达到|≥|>=|大于等于)?\s*(\d+(?:\.\d+)?)\s*(万元|万|元)?",
    )
    for pattern in patterns:
        match = re.search(pattern, content)
        if not match:
            continue
        amount = float(match.group(1))
        unit = match.group(2) or "万"
        return amount / 10000 if unit == "元" else amount
    return None


async def _match_performance_requirement(requirement: TenderRequirement) -> dict[str, Any]:
    """用 performance_projects 表本地匹配业绩要求，不依赖 LLM。"""
    req_text = requirement.content or requirement.title or ""
    required_amount = _extract_required_contract_amount(req_text)
    query_tokens = _tokenize_match_text(req_text)

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, project_name, client_name, contract_amount, project_scope, year, file_ids
               FROM performance_projects
               ORDER BY id"""
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        return {
            "status": "unmatched",
            "reason": "业绩库中暂无业绩项目",
            "mismatch_detail": f"① 不符合点: 未找到业绩项目\n② 期望资质: {req_text}\n③ 知识库检查: 未上传或未解析业绩项目",
            "expected_qualification": req_text,
            "in_knowledge_base": False,
            "similarity_score": 0.0,
        }

    candidates: list[tuple[float, Any, Optional[float]]] = []
    for row in rows:
        project_text = " ".join(
            str(row[field] or "")
            for field in ("project_name", "client_name", "contract_amount", "project_scope", "year")
        )
        token_score = _score_qualification_match(req_text, query_tokens, project_text)
        amount = _parse_amount_to_wan(row["contract_amount"])
        amount_score = 0.0
        if required_amount is not None and amount is not None:
            amount_score = 0.65 if amount >= required_amount else 0.15
        elif required_amount is None:
            amount_score = 0.35
        score = min(1.0, token_score + amount_score)
        candidates.append((score, row, amount))

    candidates.sort(key=lambda item: item[0], reverse=True)
    matched: list[tuple[float, Any, Optional[float]]] = []
    if required_amount is not None:
        matched = [
            (score, row, amount)
            for score, row, amount in candidates
            if amount is not None and amount >= required_amount
        ]
    else:
        # 没有金额、时间等可规则核验字段时，不能仅凭“业绩”泛词自动通过。
        matched = [
            (score, row, amount)
            for score, row, amount in candidates
            if score >= 0.7
        ]

    if matched:
        score, row, amount = matched[0]
        amount_text = f"{amount:g}万" if amount is not None else (row["contract_amount"] or "金额未识别")
        evidence_items = [
            _evidence_item(
                "performance_relevance",
                "业绩相关性",
                req_text,
                row["project_scope"] or row["project_name"],
                "pass",
                "业绩项目与要求存在高相关字段",
            )
        ]
        if required_amount is not None:
            evidence_items.append(
                _evidence_item(
                    "contract_amount",
                    "合同金额",
                    f"不低于 {required_amount:g}万",
                    amount_text,
                    "pass",
                    "合同金额满足要求",
                )
            )
        return {
            "status": "matched",
            "reason": (
                f"业绩库匹配到项目：{row['project_name']}；"
                f"客户：{row['client_name'] or '—'}；合同金额：{amount_text}；"
                f"年度：{row['year'] or '—'}"
            ),
            "mismatch_detail": None,
            "expected_qualification": None,
            "in_knowledge_base": True,
            "similarity_score": max(score, 0.7),
            "evidence_items": evidence_items,
        }

    best_score, best_row, best_amount = candidates[0]
    best_amount_text = f"{best_amount:g}万" if best_amount is not None else (best_row["contract_amount"] or "金额未识别")
    required_text = f"{required_amount:g}万" if required_amount is not None else "未指定"
    if required_amount is None:
        return {
            "status": "needs_review",
            "reason": "业绩要求缺少可自动核验字段，需人工确认",
            "mismatch_detail": (
                f"① 需人工确认: 要求仅表述为业绩真实性/有效性，缺少金额、时间、项目类型等可自动核验字段\n"
                f"② 期望资质: {req_text}\n"
                f"③ 知识库检查: 业绩库有候选项目「{best_row['project_name']}」，但不能自动判定满足"
            ),
            "expected_qualification": req_text,
            "in_knowledge_base": True,
            "similarity_score": best_score,
            "evidence_items": [
                _evidence_item(
                    "performance_relevance",
                    "业绩相关性",
                    req_text,
                    best_row["project_scope"] or best_row["project_name"],
                    "unknown",
                    "缺少可自动核验字段，不能仅凭候选业绩自动通过",
                )
            ],
        }
    return {
        "status": "unmatched",
        "reason": "业绩库有项目，但未找到满足要求的业绩",
        "mismatch_detail": (
            f"① 不符合点: 最接近项目「{best_row['project_name']}」合同金额 {best_amount_text}，"
            f"要求不低于 {required_text}\n"
            f"② 期望资质: {req_text}\n"
            f"③ 知识库检查: 已上传业绩项目，但金额/条件不满足"
        ),
        "expected_qualification": req_text,
        "in_knowledge_base": True,
        "similarity_score": best_score,
        "evidence_items": [
            _evidence_item(
                "contract_amount",
                "合同金额",
                f"不低于 {required_text}",
                best_amount_text,
                "fail",
                "最接近业绩的合同金额不满足要求",
            )
        ],
    }


async def _semantic_match(
    tender_id: int, requirement: TenderRequirement
) -> tuple[Optional[int], float, str]:
    """使用 SQLite 内资质字段做轻量语义匹配。

    Args:
        tender_id: 标书 ID。
        requirement: 标书要求。

    Returns:
        (匹配的资质 ID, 相似度分数, 匹配原因)。
    """
    query_text = requirement.content or requirement.title or ""
    if not query_text:
        return None, 0.0, "要求描述为空"

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, name, number, issuing_authority, scope, level, holder, category
               FROM qualifications
               WHERE status IS NULL OR status != 'needs_completion'
               ORDER BY id"""
        )
        all_quals = await cursor.fetchall()
    finally:
        await db.close()

    query_tokens = _tokenize_match_text(query_text)
    best_qual_id: Optional[int] = None
    best_score = 0.0
    best_name = ""

    for qual in all_quals:
        qual_text = " ".join(
            str(qual[field] or "")
            for field in ("name", "number", "issuing_authority", "scope", "level", "holder", "category")
        )
        score = _score_qualification_match(query_text, query_tokens, qual_text)
        if score > best_score:
            best_score = score
            best_qual_id = qual["id"]
            best_name = qual["name"] or ""

    if best_qual_id is not None and best_score >= 0.35:
        return best_qual_id, best_score, f"SQLite 字段匹配到资质: {best_name}"
    return None, 0.0, "知识库中未找到字段匹配的资质"


async def _llm_judge_match(
    requirement: TenderRequirement, qualification_name: Optional[str]
) -> tuple[str, str]:
    """使用 LLM 判断要求与资质的匹配程度。

    对于模糊要求（非数值规则），调用 LLM 做语义判断。

    Args:
        requirement: 标书要求。
        qualification_name: 资质名称，None 表示知识库中无匹配。

    Returns:
        (匹配状态: matched/unmatched/needs_review, 原因说明)。
    """
    if qualification_name is None:
        return "unmatched", "知识库中未找到相关资质"

    try:
        llm_func = await get_llm_func()

        prompt = f"""请判断以下资质是否满足标书要求：

标书要求：{requirement.content or requirement.title}
知识库资质：{qualification_name}

请只输出以下三个词之一：
- matched（符合）
- unmatched（不符合）
- needs_review（需人工确认）"""

        response = await llm_func(
            prompt,
            system_prompt="你是一个资质匹配判断助手。请准确判断资质是否满足要求。",
            temperature=0.1,
            max_tokens=50,
        )

        result = response.strip().lower()
        if "matched" in result and "un" not in result:
            return "matched", f"LLM 判断: 资质「{qualification_name}」符合要求"
        elif "unmatched" in result:
            return "unmatched", f"LLM 判断: 资质「{qualification_name}」不符合要求"
        else:
            return "needs_review", f"LLM 判断: 资质「{qualification_name}」需人工确认"

    except Exception as e:
        logger.warning("LLM 判断失败: %s", str(e))
        return "needs_review", f"LLM 判断异常，需人工确认: {str(e)}"


async def match_tender(tender_id: int) -> list[MatchResult]:
    """执行标书匹配流程。

    流程：
    1. 获取标书所有 TenderRequirement
    2. 获取知识库所有 Qualification
    3. 对每个 requirement：
       a. 语义匹配：RAG 检索相关资质
       b. 规则校验：5 类数值规则
       c. LLM 语义判断
       d. 生成 MatchResult（含不符合点、期望资质、知识库检查）
    4. 清除旧匹配结果，插入新结果

    Args:
        tender_id: 标书 ID。

    Returns:
        MatchResult 列表。
    """
    logger.info("开始匹配标书: tender_id=%s", tender_id)
    _set_match_progress(
        tender_id,
        status="running",
        stage="loading",
        message="正在读取标书要求和资质库",
        current=0,
        total=0,
        matched=0,
        unmatched=0,
        needs_review=0,
        error=None,
        finished_at=None,
    )

    # 获取标书要求
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tender_requirements WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        )
        req_rows = await cursor.fetchall()

        cursor = await db.execute("SELECT * FROM qualifications ORDER BY id")
        qual_rows = await cursor.fetchall()

        cursor = await db.execute(
            """SELECT * FROM custom_rules
               WHERE enabled = 1 AND rule_type = 'tighten_rule'
               ORDER BY id"""
        )
        custom_tighten_rule_rows = await cursor.fetchall()

        # 清除旧匹配结果
        await db.execute("DELETE FROM match_results WHERE tender_id = ?", (tender_id,))
        await db.commit()
    finally:
        await db.close()

    requirements = [TenderRequirement(**dict(r)) for r in req_rows]
    qualifications = [dict(r) for r in qual_rows]
    custom_tighten_rules = [dict(r) for r in custom_tighten_rule_rows]
    matchable_requirements = [req for req in requirements if _should_match(req)]
    total_matchable = len(matchable_requirements)

    _set_match_progress(
        tender_id,
        status="running",
        stage="matching",
        current=0,
        total=total_matchable,
        message=f"已读取 {len(requirements)} 条要求，其中 {total_matchable} 条需要资质匹配",
    )

    if not requirements:
        logger.warning("标书无要求，跳过匹配: tender_id=%s", tender_id)
        _set_match_progress(
            tender_id,
            status="completed",
            stage="completed",
            current=0,
            total=0,
            message="标书没有可匹配要求",
            finished_at=_now_iso(),
        )
        return []

    results: list[MatchResult] = []
    now = _now_iso()
    processed = 0

    for req in requirements:
        # 匹配分流：product_spec / submission 类跳过，仅 capability 类走匹配
        if not _should_match(req):
            logger.info(
                "跳过匹配: req_id=%s, category=%s, nature=%s",
                req.id, req.category, req.requirement_nature,
            )
            continue

        logger.info("匹配要求: req_id=%s, category=%s, title=%s", req.id, req.category, req.title)
        processed += 1
        _set_match_progress(
            tender_id,
            status="running",
            stage="matching",
            current=processed,
            total=total_matchable,
            current_requirement=req.title or req.content or f"要求 {req.id}",
            message=f"正在匹配第 {processed}/{total_matchable} 条要求",
        )

        if req.category == "performance":
            performance_match = await _match_performance_requirement(req)
            result = MatchResult(
                tender_id=tender_id,
                requirement_id=req.id or 0,
                qualification_id=None,
                status=performance_match["status"],
                reason=performance_match["reason"],
                mismatch_detail=performance_match["mismatch_detail"],
                expected_qualification=performance_match["expected_qualification"],
                in_knowledge_base=performance_match["in_knowledge_base"],
                similarity_score=performance_match["similarity_score"],
                evidence_items=performance_match.get("evidence_items", []),
                confirmed_status=None,
                created_at=now,
            )
            results.append(result)
            _set_match_progress(
                tender_id,
                matched=sum(1 for r in results if r.status == "matched"),
                unmatched=sum(1 for r in results if r.status == "unmatched"),
                needs_review=sum(1 for r in results if r.status == "needs_review"),
                message=f"已完成第 {processed}/{total_matchable} 条要求",
            )

            db = await get_db()
            try:
                await db.execute(
                    """INSERT INTO match_results
                       (tender_id, requirement_id, qualification_id, status, reason,
                        mismatch_detail, expected_qualification, in_knowledge_base,
                        similarity_score, evidence_items, confirmed_status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.tender_id,
                        result.requirement_id,
                        result.qualification_id,
                        result.status,
                        result.reason,
                        result.mismatch_detail,
                        result.expected_qualification,
                        1 if result.in_knowledge_base else 0,
                        result.similarity_score,
                        json.dumps([item.model_dump() for item in result.evidence_items], ensure_ascii=False),
                        result.confirmed_status,
                        now,
                    ),
                )
                await db.commit()
            finally:
                await db.close()
            continue

        # 步骤 a：语义匹配
        matched_qual_id, similarity, match_reason = await _semantic_match(tender_id, req)

        # 获取匹配到的资质信息
        matched_qual: Optional[dict[str, Any]] = None
        if matched_qual_id is not None:
            matched_qual = next(
                (q for q in qualifications if q["id"] == matched_qual_id), None
            )

        # 步骤 b：规则校验
        req_content = req.content or req.title or ""
        req_numeric = _parse_numeric_from_requirement(req_content)

        status = "needs_review"
        mismatch_detail: Optional[str] = None
        expected_qualification: Optional[str] = None
        in_knowledge_base = matched_qual is not None
        evidence_items: list[MatchEvidenceItem] = []

        if req_numeric is not None:
            # 数值规则校验
            rule_type = req_numeric["rule_type"]
            qual_value = None
            if matched_qual:
                qual_value = _parse_numeric_from_qualification(
                    matched_qual.get("name", ""),
                    matched_qual.get("scope", ""),
                    rule_type,
                )

            satisfied, detail = _check_numeric_rule(req_numeric, qual_value)

            if satisfied:
                status = "matched"
                mismatch_detail = None
            else:
                status = "unmatched"
                mismatch_detail = (
                    f"① 不符合点: {detail}\n"
                    f"② 期望资质: {req_content}\n"
                    f"③ 知识库检查: "
                    f"{'已上传相关文件但数值不满足' if in_knowledge_base else '未上传相关资质文件，请检查是否已有该资质'}"
                )
                expected_qualification = req_content

        else:
            # 非数值要求：先对候选资质做字段级证据核验；低置信候选再交给 LLM 标为待确认/不通过
            qual_name = matched_qual.get("name") if matched_qual else None
            if matched_qual and similarity >= 0.7:
                status, evidence_reason, mismatch_detail, evidence_items = (
                    _verify_qualification_evidence(req, matched_qual, similarity)
                )
                match_reason = f"{evidence_reason}: {qual_name}"
            else:
                llm_status, llm_reason = await _llm_judge_match(req, qual_name)
                status = llm_status

            if status == "unmatched":
                if not mismatch_detail:
                    mismatch_detail = (
                        f"① 不符合点: {llm_reason}\n"
                        f"② 期望资质: {req_content}\n"
                        f"③ 知识库检查: "
                        f"{'已上传但不符合要求' if in_knowledge_base else '未上传相关资质文件，请检查是否已有该资质'}"
                    )
                expected_qualification = req_content
            elif status == "needs_review":
                if not mismatch_detail:
                    mismatch_detail = (
                        f"① 需人工确认: {llm_reason}\n"
                        f"② 期望资质: {req_content}\n"
                        f"③ 知识库检查: "
                        f"{'已上传相关文件' if in_knowledge_base else '未上传相关资质文件'}"
                    )
                expected_qualification = req_content

        status, match_reason, mismatch_detail, expected_qualification, evidence_items = (
            _apply_custom_tighten_rules(
                req,
                status,
                match_reason,
                mismatch_detail,
                expected_qualification,
                evidence_items,
                custom_tighten_rules,
            )
        )

        # 创建 MatchResult
        result = MatchResult(
            tender_id=tender_id,
            requirement_id=req.id or 0,
            qualification_id=matched_qual_id,
            status=status,
            reason=match_reason,
            mismatch_detail=mismatch_detail,
            expected_qualification=expected_qualification,
            in_knowledge_base=in_knowledge_base,
            similarity_score=similarity,
            evidence_items=evidence_items,
            confirmed_status=None,
            created_at=now,
        )
        results.append(result)
        _set_match_progress(
            tender_id,
            matched=sum(1 for r in results if r.status == "matched"),
            unmatched=sum(1 for r in results if r.status == "unmatched"),
            needs_review=sum(1 for r in results if r.status == "needs_review"),
            message=f"已完成第 {processed}/{total_matchable} 条要求",
        )

        # 插入数据库
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO match_results
                   (tender_id, requirement_id, qualification_id, status, reason,
                    mismatch_detail, expected_qualification, in_knowledge_base,
                    similarity_score, evidence_items, confirmed_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.tender_id,
                    result.requirement_id,
                    result.qualification_id,
                    result.status,
                    result.reason,
                    result.mismatch_detail,
                    result.expected_qualification,
                    1 if result.in_knowledge_base else 0,
                    result.similarity_score,
                    json.dumps([item.model_dump() for item in result.evidence_items], ensure_ascii=False),
                    result.confirmed_status,
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()

    logger.info(
        "标书匹配完成: tender_id=%s, total=%d, matched=%d, unmatched=%d, needs_review=%d",
        tender_id,
        len(results),
        sum(1 for r in results if r.status == "matched"),
        sum(1 for r in results if r.status == "unmatched"),
        sum(1 for r in results if r.status == "needs_review"),
    )
    _set_match_progress(
        tender_id,
        status="completed",
        stage="completed",
        current=total_matchable,
        total=total_matchable,
        matched=sum(1 for r in results if r.status == "matched"),
        unmatched=sum(1 for r in results if r.status == "unmatched"),
        needs_review=sum(1 for r in results if r.status == "needs_review"),
        current_requirement=None,
        message="匹配完成",
        finished_at=_now_iso(),
    )

    return results


async def match_tender_background(tender_id: int) -> None:
    """Run matching and record failure state for UI polling."""
    try:
        await match_tender(tender_id)
    except Exception as exc:
        logger.exception("标书匹配后台任务失败: tender_id=%s", tender_id)
        _set_match_progress(
            tender_id,
            status="failed",
            stage="failed",
            message="匹配任务失败",
            error=str(exc),
            finished_at=_now_iso(),
        )


async def get_match_results(tender_id: int) -> list[MatchResult]:
    """获取标书的匹配结果列表。

    Args:
        tender_id: 标书 ID。

    Returns:
        MatchResult 列表。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM match_results WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        results: list[MatchResult] = []

        for row in rows:
            data = dict(row)

            req_cursor = await db.execute(
                "SELECT * FROM tender_requirements WHERE id = ?",
                (data["requirement_id"],),
            )
            req_row = await req_cursor.fetchone()
            if req_row is not None:
                data["requirement"] = dict(req_row)

            if data.get("qualification_id") is not None:
                qual_cursor = await db.execute(
                    "SELECT * FROM qualifications WHERE id = ?",
                    (data["qualification_id"],),
                )
                qual_row = await qual_cursor.fetchone()
                if qual_row is not None:
                    data["qualification"] = dict(qual_row)

            results.append(MatchResult(**data))

        return results
    finally:
        await db.close()


async def list_match_corrections(limit: int = 100) -> list[dict[str, Any]]:
    """List human correction cases with display context."""
    safe_limit = max(1, min(limit, 500))
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT
                   mc.id,
                   mc.match_id,
                   mc.tender_id,
                   mc.requirement_id,
                   mc.qualification_id,
                   mc.previous_status,
                   mc.confirmed_status,
                   mc.correction_reason,
                   mc.evidence_snapshot,
                   mc.created_at,
                   t.title AS tender_title,
                   t.filename AS tender_filename,
                   tr.title AS requirement_title,
                   tr.content AS requirement_content,
                   tr.category AS requirement_category,
                   q.name AS qualification_name
               FROM match_corrections mc
               LEFT JOIN tenders t ON t.id = mc.tender_id
               LEFT JOIN tender_requirements tr ON tr.id = mc.requirement_id
               LEFT JOIN qualifications q ON q.id = mc.qualification_id
               ORDER BY mc.id DESC
               LIMIT ?""",
            (safe_limit,),
        )
        rows = await cursor.fetchall()
        corrections: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_snapshot = item.get("evidence_snapshot")
            try:
                item["evidence_snapshot"] = json.loads(raw_snapshot) if raw_snapshot else []
            except json.JSONDecodeError:
                item["evidence_snapshot"] = []
            corrections.append(item)
        return corrections
    finally:
        await db.close()


async def clear_match_results(tender_id: int) -> int:
    """清除某份标书的历史匹配结果，返回删除数量。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM match_results WHERE tender_id = ?",
            (tender_id,),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


async def confirm_match(
    match_id: int,
    confirmed_status: str,
    correction_reason: str | None = None,
) -> Optional[MatchResult]:
    """人工确认匹配结果（P1-02）。

    Args:
        match_id: 匹配结果 ID。
        confirmed_status: 确认状态（matched/unmatched/needs_review/confirmed）。
        correction_reason: 人工修正原因，用于沉淀错例。

    Returns:
        更新后的 MatchResult 实例，不存在时返回 None。
    """
    clean_correction_reason = correction_reason.strip() if correction_reason else ""
    if not clean_correction_reason:
        return None

    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM match_results WHERE id = ?", (match_id,))
        before_row = await cursor.fetchone()
        if before_row is None:
            return None
        before = dict(before_row)

        await db.execute(
            "UPDATE match_results SET confirmed_status = ? WHERE id = ?",
            (confirmed_status, match_id),
        )
        await db.execute(
            """INSERT INTO match_corrections
               (match_id, tender_id, requirement_id, qualification_id, previous_status,
                confirmed_status, correction_reason, evidence_snapshot, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match_id,
                before["tender_id"],
                before["requirement_id"],
                before.get("qualification_id"),
                before.get("status"),
                confirmed_status,
                clean_correction_reason,
                before.get("evidence_items"),
                _now_iso(),
            ),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM match_results WHERE id = ?", (match_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return MatchResult(**dict(row))
    finally:
        await db.close()
