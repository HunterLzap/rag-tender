import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, Decision, Requirement
from app.services.retrieval import normalize_cn


def load_golden_set(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def match_expected(
    extracted: list[Requirement],
    expected: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_expected: set[int] = set()
    located = 0
    for requirement in extracted:
        quote = normalize_cn(requirement.statement)
        hit_index = None
        for index, item in enumerate(expected):
            if index in matched_expected:
                continue
            if normalize_cn(item.get("statement", "")) in quote:
                hit_index = index
                break
        if hit_index is not None:
            matched_expected.add(hit_index)
            if requirement.source_span_id:
                located += 1
    return {
        "expected_count": len(expected),
        "extracted_count": len(extracted),
        "matched_count": len(matched_expected),
        "recall": len(matched_expected) / max(len(expected), 1),
        "location_rate": located / max(len(extracted), 1),
        "missing": [
            item.get("title")
            for index, item in enumerate(expected)
            if index not in matched_expected
        ],
    }


async def evaluate_run(
    session: AsyncSession,
    run_id: str,
    golden: dict[str, Any],
    *,
    min_recall: float = 0.9,
    min_location_rate: float = 0.95,
) -> dict[str, Any]:
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError("分析任务不存在")
    requirements = (
        await session.execute(select(Requirement).where(Requirement.run_id == run_id))
    ).scalars().all()
    decisions = (
        await session.execute(select(Decision).where(Decision.run_id == run_id))
    ).scalars().all()
    extraction = match_expected(requirements, golden.get("requirements", []))
    false_met = 0
    for decision in decisions:
        requirement = next(
            (item for item in requirements if item.id == decision.requirement_id), None
        )
        if requirement is None or decision.status.value != "met":
            continue
        if any(
            normalize_cn(item.get("statement", "")) in normalize_cn(requirement.statement)
            and item.get("expected_status") in {"not_met", "needs_review"}
            for item in golden.get("requirements", [])
        ):
            false_met += 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        **extraction,
        "false_met": false_met,
        "passed": (
            extraction["recall"] >= min_recall
            and extraction["location_rate"] >= min_location_rate
            and false_met == 0
        ),
        "thresholds": {
            "min_recall": min_recall,
            "min_location_rate": min_location_rate,
            "max_false_met": 0,
        },
    }
