import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvidenceFact, EvidenceItem, EvidenceStatus


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence: EvidenceItem
    score: float
    reasons: tuple[str, ...]


def normalize_cn(value: str) -> str:
    text = re.sub(r"\s+", "", value or "").lower()
    replacements = {
        "（": "(",
        "）": ")",
        "：": ":",
        "，": ",",
        "。": ".",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def bigrams(value: str) -> set[str]:
    text = normalize_cn(value)
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


def lexical_score(query: str, document: str) -> float:
    query_grams = bigrams(query)
    document_grams = bigrams(document)
    if not query_grams or not document_grams:
        return 0.0
    return len(query_grams & document_grams) / len(query_grams)


async def recall_evidence(
    session: AsyncSession,
    *,
    project_id: str,
    kind: str,
    query: str,
    limit: int = 8,
) -> list[EvidenceCandidate]:
    rows = (
        await session.execute(
            select(EvidenceItem).where(
                EvidenceItem.kind == kind,
                EvidenceItem.status == EvidenceStatus.ACTIVE,
                (EvidenceItem.project_id == project_id)
                | (EvidenceItem.organization_id.is_not(None)),
            )
        )
    ).scalars()
    candidates: list[EvidenceCandidate] = []
    for evidence in rows:
        facts = (
            await session.execute(
                select(EvidenceFact).where(EvidenceFact.evidence_id == evidence.id)
            )
        ).scalars()
        fact_text = " ".join(
            str(value)
            for fact in facts
            for value in (fact.fact_key, fact.value_text, fact.holder, fact.unit)
            if value
        )
        corpus = " ".join(
            filter(
                None,
                [
                    evidence.title,
                    evidence.holder,
                    evidence.issuer,
                    evidence.identifier,
                    fact_text,
                    str(evidence.payload or ""),
                ],
            )
        )
        score = lexical_score(query, corpus)
        if score < 0.02:
            continue
        reasons = [f"文本重合度 {score:.0%}"]
        if evidence.holder and normalize_cn(evidence.holder) in normalize_cn(query):
            score = min(1.0, score + 0.25)
            reasons.append("主体命中")
        candidates.append(
            EvidenceCandidate(
                evidence=evidence,
                score=round(score, 4),
                reasons=tuple(reasons),
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:limit]
