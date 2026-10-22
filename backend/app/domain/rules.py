import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class RuleResult:
    key: str
    status: str
    expected: str | None
    actual: str | None
    reason: str
    critical: bool = True
    children: tuple["RuleResult", ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = {
            "key": self.key,
            "status": self.status,
            "expected": self.expected,
            "actual": self.actual,
            "reason": self.reason,
            "critical": self.critical,
        }
        if self.children:
            result["conditions"] = [item.as_dict() for item in self.children]
        return result


def evaluate_condition(
    condition: dict[str, Any],
    *,
    facts: list[Any],
    as_of: date,
    leaf_evaluator: Callable[[dict], RuleResult] | None = None,
) -> RuleResult:
    if condition.get("logic") in {"all", "any"}:
        children = condition.get("conditions") or []
        results = [
            evaluate_condition(child, facts=facts, as_of=as_of, leaf_evaluator=leaf_evaluator)
            for child in children
        ]
        if not results:
            return RuleResult(
                "condition_group",
                "unknown",
                condition.get("logic"),
                None,
                "条件组为空",
            )
        status = aggregate_status(str(condition["logic"]), [item.status for item in results])
        failed = [item for item in results if item.status == "fail"]
        unknown = [item for item in results if item.status == "unknown"]
        if status == "pass":
            reason = "组合条件满足"
        elif status == "fail":
            reason = "；".join(item.reason for item in failed) or "组合条件不满足"
        else:
            reason = "；".join(item.reason for item in unknown) or "组合条件信息不足"
        return RuleResult(
            "condition_group",
            status,
            condition.get("logic"),
            None,
            reason,
            children=tuple(results),
        )
    if leaf_evaluator:
        return leaf_evaluator(condition)
    kind = condition.get("type")
    if kind == "certificate":
        return _certificate_rule(condition, facts, as_of)
    if kind == "number":
        return _number_rule(condition, facts)
    if kind == "date":
        return _date_rule(condition, facts, as_of)
    if kind == "material_complete":
        return _material_rule(condition, facts)
    return RuleResult(
        key=str(kind or "unknown"),
        status="unknown",
        expected=None,
        actual=None,
        reason="暂无可确定的规则，需人工判断",
    )


def aggregate_status(logic: str, statuses: list[str]) -> str:
    if logic == "any":
        if "pass" in statuses:
            return "pass"
        if all(status == "fail" for status in statuses):
            return "fail"
        return "unknown"
    if "fail" in statuses:
        return "fail"
    if "unknown" in statuses:
        return "unknown"
    return "pass"


def _facts_by_key(facts: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for fact in facts:
        grouped.setdefault(fact.fact_key, []).append(fact)
    return grouped


def _certificate_rule(
    condition: dict[str, Any], facts: list[Any], as_of: date
) -> RuleResult:
    required_name = str(condition.get("certificate") or condition.get("value") or "")
    certificate_facts = [
        fact
        for fact in facts
        if fact.fact_key in {"certificate_type", "certificate_name", "qualification"}
    ]
    if not certificate_facts:
        return RuleResult("certificate", "unknown", required_name, None, "未找到证书字段")
    matching = [
        fact
        for fact in certificate_facts
        if required_name and required_name in (fact.value_text or "")
    ]
    if not matching:
        actual = certificate_facts[0].value_text
        return RuleResult(
            "certificate",
            "fail",
            required_name,
            actual,
            "证书类型与要求不一致",
        )
    expiries = [
        fact.value_date
        for fact in facts
        if fact.fact_key in {"expiry_date", "valid_until"} and fact.value_date
    ]
    if expiries and min(expiries) < as_of:
        return RuleResult(
            "certificate",
            "fail",
            f"{required_name}，投标截止日前有效",
            min(expiries).isoformat(),
            "证书在投标截止日前已过期",
        )
    if not expiries and condition.get("require_validity", True):
        return RuleResult(
            "certificate",
            "unknown",
            f"{required_name}，含有效期",
            matching[0].value_text,
            "未识别证书有效期",
        )
    return RuleResult(
        "certificate",
        "pass",
        required_name,
        matching[0].value_text,
        "证书类型匹配，有效期满足",
    )


def _number_rule(condition: dict[str, Any], facts: list[Any]) -> RuleResult:
    key = str(condition.get("key") or "")
    operator = str(condition.get("operator") or ">=")
    required = Decimal(str(condition.get("value")))
    unit = str(condition.get("unit") or "")
    values = []
    money_units = {"元": Decimal(1), "万元": Decimal(10000),
                   "万": Decimal(10000), "亿元": Decimal(100000000)}
    for fact in _facts_by_key(facts).get(key, []):
        if fact.value_number is None:
            continue
        value = fact.value_number
        actual_unit = getattr(fact, "unit", None) or ""
        if unit and actual_unit != unit:
            if unit not in money_units or actual_unit not in money_units:
                continue
            value = value * money_units[actual_unit] / money_units[unit]
        values.append(value)
    if not values:
        return RuleResult(
            key, "unknown", f"{operator}{required}{unit}", None, "未找到带明确单位的可比较数值字段"
        )
    actual = max(values)
    passed = {
        ">=": actual >= required,
        ">": actual > required,
        "<=": actual <= required,
        "<": actual < required,
        "==": actual == required,
    }.get(operator)
    if passed is None:
        return RuleResult(
            key,
            "unknown",
            f"{operator}{required}{unit}",
            str(actual),
            "不支持的运算符",
        )
    status = "pass" if passed else "fail"
    return RuleResult(
        key,
        status,
        f"{operator}{required}{unit}",
        f"{actual}{unit}",
        "数值规则满足" if passed else "数值规则不满足",
    )


def _date_rule(condition: dict[str, Any], facts: list[Any], as_of: date) -> RuleResult:
    key = str(condition.get("key") or "expiry_date")
    values = [
        fact.value_date for fact in _facts_by_key(facts).get(key, []) if fact.value_date
    ]
    if not values:
        return RuleResult(key, "unknown", as_of.isoformat(), None, "未找到日期字段")
    actual = min(values)
    passed = actual >= as_of
    return RuleResult(
        key,
        "pass" if passed else "fail",
        as_of.isoformat(),
        actual.isoformat(),
        "日期规则满足" if passed else "日期已过期",
    )


def _material_rule(condition: dict[str, Any], facts: list[Any]) -> RuleResult:
    required = condition.get("materials") or []
    if not required:
        return RuleResult(
            "material_complete", "unknown", None, None, "提交材料需逐项人工核对"
        )
    existing = {fact.fact_key for fact in facts}
    missing = [item for item in required if item not in existing]
    if missing:
        return RuleResult(
            "material_complete",
            "unknown",
            ", ".join(required),
            ", ".join(sorted(existing)),
            f"缺少材料字段: {', '.join(missing)}",
        )
    return RuleResult(
        "material_complete",
        "pass",
        ", ".join(required),
        ", ".join(sorted(existing)),
        "材料字段齐全",
    )


def extract_condition(statement: str, category: str) -> dict[str, Any]:
    amount = re.search(
        r"(?:合同金额|注册资本|营业收入)[^0-9]{0,12}(不低于|不少于|≥|>=|以上)?\s*"
        r"(\d+(?:\.\d+)?)\s*(万元|万|元)",
        statement,
    )
    if amount:
        raw = Decimal(amount.group(2))
        if amount.group(3) == "元":
            raw = raw / Decimal(10000)
        key = "registered_capital" if "注册资本" in statement else "contract_amount"
        if "营业收入" in statement:
            key = "revenue"
        return {
            "type": "number",
            "key": key,
            "operator": ">=",
            "value": str(raw),
            "unit": "万元",
        }
    cert = re.search(r"(ISO\s?\d{4,5}|CCC|3C|资质证书|安全生产许可证)", statement, re.I)
    if cert:
        return {
            "type": "certificate",
            "certificate": cert.group(1).replace(" ", "").upper(),
            "require_validity": True,
        }
    if category == "submission":
        return {"type": "material_complete", "materials": []}
    return {"type": "semantic", "statement": statement}
