from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisRun,
    AnalysisStatus,
    Bid,
    Decision,
    DecisionStatus,
    EvidenceFact,
    EvidenceItem,
    Project,
    Requirement,
)
from app.services.jobs import mark_progress


async def decide_run(
    session: AsyncSession,
    run: AnalysisRun,
    *,
    job_id: str | None = None,
    config_id: str | None = None,
    use_model: bool = True,
) -> dict[str, Any]:
    from app.services.comparison import compare_requirement

    bid = await session.get(Bid, run.bid_id) if run.bid_id else None
    project = await session.get(Project, run.project_id)
    deadline = (bid.bid_deadline if bid else None) or project.bid_deadline
    timezone = ZoneInfo(project.timezone)
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    as_of = (
        bid.as_of_date
        if bid and bid.as_of_date
        else deadline.astimezone(timezone).date()
        if deadline
        else datetime.now(timezone).date()
    )
    requirements = (
        (
            await session.execute(
                select(Requirement)
                .where(
                    Requirement.run_id == run.id,
                )
                .order_by(Requirement.created_at)
            )
        )
        .scalars()
        .all()
    )
    existing = {
        item.requirement_id: item
        for item in (
            await session.execute(
                select(Decision).where(
                    Decision.run_id == run.id,
                )
            )
        ).scalars()
    }
    counts = {status.value: 0 for status in DecisionStatus}
    for index, requirement in enumerate(requirements):
        result = await compare_requirement(
            session,
            project=project,
            requirement=requirement,
            as_of=as_of,
            use_model=use_model,
            job_id=job_id,
            config_id=config_id,
        )
        decision = existing.get(requirement.id)
        if decision is None:
            decision = Decision(run_id=run.id, requirement_id=requirement.id)
            session.add(decision)
        for key, value in result.items():
            setattr(decision, key, value)
        decision.stale = False
        counts[decision.status.value] += 1
        if job_id:
            await mark_progress(
                session,
                job_id,
                progress=70 + int((index + 1) / max(len(requirements), 1) * 18),
                stage=f"对标要求 {index + 1}/{len(requirements)}",
            )
    run.status = (
        AnalysisStatus.NEEDS_REVIEW
        if counts[DecisionStatus.NEEDS_REVIEW.value]
        else AnalysisStatus.COMPLETED
    )
    run.stage = "decisions_completed"
    run.progress = 88
    await session.commit()
    return counts


async def enrich_evidence_facts(
    session: AsyncSession,
    evidence: EvidenceItem,
    payload: dict[str, Any],
) -> list[EvidenceFact]:
    facts: list[EvidenceFact] = []
    mapping = {
        "certificate_name": "value_text",
        "certificate_type": "value_text",
        "level": "value_text",
        "scope": "value_text",
        "registered_capital": "value_number",
        "revenue": "value_number",
        "contract_amount": "value_number",
        "expiry_date": "value_date",
        "issue_date": "value_date",
        "project_name": "value_text",
        "client_name": "value_text",
        "project_scope": "value_text",
        "debt_ratio": "value_number",
    }
    for key, value in payload.items():
        if value is None or key not in mapping:
            continue
        column = mapping[key]
        if column == "value_number":
            number = Decimal(str(value)) if not isinstance(value, Decimal) else value
            fact = EvidenceFact(
                evidence_id=evidence.id,
                fact_key=key,
                value_number=number,
                unit=payload.get("unit"),
                currency=payload.get("currency"),
                holder=evidence.holder,
                source_span_id=evidence.source_span_id,
                extraction_method="manual",
                review_status=evidence.review_status,
            )
        elif column == "value_date":
            try:
                parsed = date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
            fact = EvidenceFact(
                evidence_id=evidence.id,
                fact_key=key,
                value_date=parsed,
                holder=evidence.holder,
                source_span_id=evidence.source_span_id,
                extraction_method="manual",
                review_status=evidence.review_status,
            )
        else:
            fact = EvidenceFact(
                evidence_id=evidence.id,
                fact_key=key,
                value_text=str(value),
                holder=evidence.holder,
                source_span_id=evidence.source_span_id,
                extraction_method="manual",
                review_status=evidence.review_status,
            )
        session.add(fact)
        facts.append(fact)
    if evidence.valid_until:
        fact = EvidenceFact(
            evidence_id=evidence.id,
            fact_key="valid_until",
            value_date=evidence.valid_until,
            holder=evidence.holder,
            source_span_id=evidence.source_span_id,
            extraction_method="manual",
            review_status=evidence.review_status,
        )
        session.add(fact)
        facts.append(fact)
    return facts
