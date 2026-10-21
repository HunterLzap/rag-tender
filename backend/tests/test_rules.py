from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.domain.rules import evaluate_condition
from app.models import Requirement, RequirementReviewStatus
from app.services.decision_engine import decide_requirement


def fact(key, **kwargs):
    return SimpleNamespace(fact_key=key, **kwargs)


def test_certificate_validity_uses_bid_deadline():
    result = evaluate_condition(
        {"type": "certificate", "certificate": "ISO9001"},
        facts=[
            fact("certificate_type", value_text="ISO9001 质量管理体系"),
            fact("valid_until", value_date=date(2024, 1, 1)),
        ],
        as_of=date(2024, 2, 1),
    )
    assert result.status == "fail"


def test_missing_number_fact_is_unknown_not_pass():
    result = evaluate_condition(
        {"type": "number", "key": "registered_capital", "operator": ">=", "value": "1000"},
        facts=[],
        as_of=date(2024, 1, 1),
    )
    assert result.status == "unknown"


def test_composite_any_condition():
    result = evaluate_condition(
        {
            "type": "group",
            "logic": "any",
            "conditions": [
                {"type": "certificate", "certificate": "ISO9001"},
                {"type": "certificate", "certificate": "CCC"},
            ],
        },
        facts=[
            fact("certificate_type", value_text="CCC 认证"),
            fact("valid_until", value_date=date(2026, 1, 1)),
        ],
        as_of=date(2024, 1, 1),
    )
    assert result.status == "pass"


def test_mandatory_requirement_without_evidence_needs_review():
    requirement = Requirement(
        run_id="r",
        category="qualification",
        title="ISO9001",
        statement="须具有 ISO9001",
        condition_json={"type": "semantic"},
        source_span_id="s",
        fingerprint="f",
        obligation="mandatory",
        review_status=RequirementReviewStatus.UNREVIEWED,
    )
    status, summary, _, _ = decide_requirement(
        requirement, as_of=date(2024, 1, 1), facts=[]
    )
    assert status.value == "needs_review"
    assert "证据" in summary


def test_number_rule_converts_currency_units_and_requires_known_units():
    condition = {
        "type": "number", "key": "contract_amount", "operator": ">=",
        "value": "1000", "unit": "万元",
    }
    result = evaluate_condition(
        condition,
        facts=[fact("contract_amount", value_number=Decimal("5000000"), unit="元")],
        as_of=date(2026, 1, 1),
    )
    assert result.status == "fail"
    assert result.actual == "500万元"
    missing_unit = evaluate_condition(
        condition,
        facts=[fact("contract_amount", value_number=Decimal("5000000"))],
        as_of=date(2026, 1, 1),
    )
    assert missing_unit.status == "unknown"
