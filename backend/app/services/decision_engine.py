from datetime import date
from typing import Any

from app.domain.rules import RuleResult, evaluate_condition
from app.models import DecisionStatus, Requirement, RequirementReviewStatus


def decide_requirement(
    requirement: Requirement,
    *,
    as_of: date,
    facts: list[Any],
    model_assessment: str | None = None,
) -> tuple[DecisionStatus, str, list[dict[str, Any]], list[dict[str, Any]]]:
    condition = requirement.condition_json or {}
    result: RuleResult = evaluate_condition(condition, facts=facts, as_of=as_of)
    trace = [result.as_dict()]

    if requirement.review_status == RequirementReviewStatus.REJECTED:
        return (
            DecisionStatus.NOT_APPLICABLE,
            "要求已被人工否决",
            trace,
            [],
        )

    if result.status == "fail":
        return (
            DecisionStatus.NOT_MET,
            result.reason,
            trace,
            [],
        )

    if result.status == "unknown":
        if model_assessment == "supports":
            return (
                DecisionStatus.NEEDS_REVIEW,
                f"{result.reason}；模型判断可能有支持证据，但关键字段仍不完整",
                trace,
                [],
            )
        if requirement.obligation == "mandatory" and not facts:
            return (
                DecisionStatus.NEEDS_REVIEW,
                "硬性要求缺少证据链，需人工补齐或确认",
                trace,
                [],
            )
        return (
            DecisionStatus.NEEDS_REVIEW,
            result.reason,
            trace,
            [],
        )

    if model_assessment == "contradicts":
        return (
            DecisionStatus.NEEDS_REVIEW,
            "确定性规则通过，但模型判断存在矛盾，需人工复核",
            trace,
            [],
        )

    if requirement.obligation == "mandatory" and not facts:
        return (
            DecisionStatus.NEEDS_REVIEW,
            "硬性要求缺少证据链",
            trace,
            [],
        )

    return (
        DecisionStatus.MET,
        "关键规则与证据检查通过",
        trace,
        [],
    )


def aggregate_condition_results(
    group: dict[str, Any], results: list[RuleResult]
) -> str:
    logic = group.get("logic", "all")
    statuses = [result.status for result in results]
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
