import math
import re
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Document,
    EmbeddingRecord,
    EvidenceFact,
    EvidenceItem,
    EvidenceReviewStatus,
    EvidenceStatus,
    Project,
    SearchChunk,
    SourceSpan,
)
from app.services.library import document_scope, evidence_scope, search_tokens
from app.services.model_gateway import embed_texts


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence: EvidenceItem
    score: float
    reasons: tuple[str, ...]
    source_span_ids: tuple[str, ...] = ()


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
    kind: str | None,
    query: str,
    limit: int = 8,
    use_embeddings: bool = False,
    job_id: str | None = None,
    config_id: str | None = None,
) -> list[EvidenceCandidate]:
    project = await session.get(Project, project_id)
    if project is None:
        return []
    chunks = (
        (
            await session.execute(
                select(SearchChunk)
                .join(Document, SearchChunk.document_id == Document.id)
                .where(
                    document_scope(project), SearchChunk.revision_id == Document.current_revision_id
                )
            )
        )
        .scalars()
        .all()
    )
    chunk_scores: dict[str, float] = {}
    if chunks and session.bind.dialect.name == "sqlite":
        query_tokens = list(dict.fromkeys(search_tokens(query).split()))[:80]
        if query_tokens:
            keyword = (
                (
                    await session.execute(
                        text(
                            "SELECT c.id FROM search_chunks_fts "
                            "JOIN search_chunks c ON c.id=search_chunks_fts.chunk_id "
                            "JOIN documents d ON d.id=c.document_id "
                            "WHERE search_chunks_fts MATCH :query "
                            "AND c.revision_id=d.current_revision_id "
                            "AND (d.project_id=:project OR (:organization IS NOT NULL "
                            "AND d.organization_id=:organization)) "
                            "ORDER BY bm25(search_chunks_fts) LIMIT 80"
                        ),
                        {
                            "query": " OR ".join(f'"{word}"' for word in query_tokens),
                            "project": project.id,
                            "organization": project.organization_id,
                        },
                    )
                )
                .scalars()
                .all()
            )
            for rank, chunk_id in enumerate(keyword):
                chunk_scores[chunk_id] = 1 / (60 + rank)
    if use_embeddings and chunks:
        signature, records = await embed_texts(
            session,
            [query],
            job_id=job_id,
            config_id=config_id,
        )
        query_vector = records[0].vector
        vectors = {
            record.id: record.vector
            for record in (
                await session.execute(
                    select(EmbeddingRecord).where(
                        EmbeddingRecord.id.in_([chunk.embedding_id for chunk in chunks]),
                        EmbeddingRecord.model_signature == signature,
                    )
                )
            ).scalars()
        }
        ranked = sorted(
            (
                (chunk.id, cosine(query_vector, vectors[chunk.embedding_id]))
                for chunk in chunks
                if chunk.embedding_id in vectors
            ),
            key=lambda row: row[1],
            reverse=True,
        )[:80]
        for rank, (chunk_id, similarity) in enumerate(ranked):
            if similarity > 0:
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1 / (60 + rank)
    by_document: dict[str, list[SearchChunk]] = {}
    for chunk in sorted(chunks, key=lambda item: chunk_scores.get(item.id, 0), reverse=True):
        if chunk_scores.get(chunk.id):
            by_document.setdefault(chunk.document_id, []).append(chunk)
    rows = (
        await session.execute(
            select(EvidenceItem, SourceSpan)
            .join(SourceSpan, EvidenceItem.source_span_id == SourceSpan.id)
            .join(Document, SourceSpan.document_id == Document.id)
            .where(
                *([EvidenceItem.kind == kind] if kind else []),
                EvidenceItem.status == EvidenceStatus.ACTIVE,
                EvidenceItem.review_status != EvidenceReviewStatus.REJECTED,
                evidence_scope(project),
                SourceSpan.revision_id == Document.current_revision_id,
            )
        )
    ).all()
    candidates: list[EvidenceCandidate] = []
    for evidence, span in rows:
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
                    span.quote,
                ],
            )
        )
        score = lexical_score(query, corpus)
        found_chunks = by_document.get(span.document_id, [])
        if found_chunks:
            score += max(chunk_scores[chunk.id] for chunk in found_chunks) * 15
        if score < 0.02 and not kind:
            continue
        reasons = ["全文与语义联合召回" if found_chunks else "结构化类型与文本召回"]
        if evidence.holder and normalize_cn(evidence.holder) in normalize_cn(query):
            score = min(1.0, score + 0.25)
            reasons.append("主体命中")
        candidates.append(
            EvidenceCandidate(
                evidence=evidence,
                score=round(score, 4),
                reasons=tuple(reasons),
                source_span_ids=tuple(chunk.source_span_id for chunk in found_chunks[:3]),
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:limit]


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    denominator = math.sqrt(
        sum(value * value for value in left) * sum(value * value for value in right)
    )
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0


async def recall_documents(
    session: AsyncSession,
    *,
    project_id: str | None,
    query: str,
    limit: int = 12,
    use_embeddings: bool = False,
    job_id: str | None = None,
    config_id: str | None = None,
) -> list[dict]:
    """Return source-preserving chunks for project/enterprise drafting."""
    project = await session.get(Project, project_id) if project_id else None
    if project is None:
        return []
    rows = (
        await session.execute(
            select(SearchChunk, SourceSpan, Document)
            .join(SourceSpan, SourceSpan.id == SearchChunk.source_span_id)
            .join(Document, Document.id == SearchChunk.document_id)
            .where(
                document_scope(project),
                SearchChunk.revision_id == Document.current_revision_id,
                Document.role.in_(["evidence", "tender", "addendum", "qa"]),
            )
        )
    ).all()
    evidence = (
        (
            await session.execute(
                select(EvidenceItem)
                .join(SourceSpan, SourceSpan.id == EvidenceItem.source_span_id)
                .join(Document, Document.id == SourceSpan.document_id)
                .where(
                    evidence_scope(project),
                    EvidenceItem.status == EvidenceStatus.ACTIVE,
                    EvidenceItem.review_status.in_(
                        [
                            EvidenceReviewStatus.VERIFIED,
                            EvidenceReviewStatus.EXTRACTED,
                        ]
                    ),
                    SourceSpan.revision_id == Document.current_revision_id,
                )
                .options(
                    selectinload(EvidenceItem.source_span),
                    selectinload(EvidenceItem.facts).selectinload(EvidenceFact.source_span),
                )
            )
        )
        .scalars()
        .all()
    )
    tokens = set(bigrams(query))
    query_vector = None
    vectors = {}
    if use_embeddings and rows:
        signature, embedded = await embed_texts(
            session,
            [query],
            job_id=job_id,
            config_id=config_id,
        )
        query_vector = embedded[0].vector
        vectors = {
            record.id: record.vector
            for record in (
                await session.execute(
                    select(EmbeddingRecord).where(
                        EmbeddingRecord.id.in_([chunk.embedding_id for chunk, _, _ in rows]),
                        EmbeddingRecord.model_signature == signature,
                    )
                )
            ).scalars()
        }
    ranked = []
    for chunk, span, document in rows:
        score = len(tokens & bigrams(chunk.text)) / max(len(tokens), 1)
        if query_vector and chunk.embedding_id in vectors:
            score += max(0.0, cosine(query_vector, vectors[chunk.embedding_id]))
        if score:
            ranked.append((score, chunk, span, document))
    ranked.sort(key=lambda item: item[0], reverse=True)
    contexts = []
    for _score, chunk, span, document in ranked[:limit]:
        items = [
            item
            for item in evidence
            if item.source_span.document_id == document.id
            and item.source_span.page_id == span.page_id
        ]
        contexts.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "filename": document.filename,
                "role": document.role,
                "page_id": span.page_id,
                "source_span_id": span.id,
                "text": chunk.text[:3500],
                "evidence_ids": [item.id for item in items],
                "facts": [
                    {
                        "key": fact.fact_key,
                        "text": fact.value_text,
                        "number": str(fact.value_number) if fact.value_number is not None else None,
                        "date": str(fact.value_date) if fact.value_date else None,
                        "unit": fact.unit,
                        "source_span_id": fact.source_span_id,
                    }
                    for item in items
                    for fact in item.facts
                    if fact.review_status
                    in {
                        EvidenceReviewStatus.VERIFIED,
                        EvidenceReviewStatus.EXTRACTED,
                    }
                    and fact.source_span
                    and fact.source_span.block_id == span.block_id
                ],
            }
        )
    return contexts
