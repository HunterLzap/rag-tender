"""Shared enterprise ownership and source-backed document indexing."""

import re

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Block,
    Document,
    EvidenceItem,
    Page,
    Project,
    SearchChunk,
    SourceSpan,
)
from app.services.model_gateway import embed_texts
from app.storage import sha256_text


def document_scope(project: Project):
    own = Document.project_id == project.id
    return (
        or_(own, Document.organization_id == project.organization_id)
        if project.organization_id
        else own
    )


def evidence_scope(project: Project):
    own = EvidenceItem.project_id == project.id
    return (
        or_(own, EvidenceItem.organization_id == project.organization_id)
        if project.organization_id
        else own
    )


async def mark_organization_stale(session: AsyncSession, organization_id: str | None) -> None:
    from app.services.freshness import mark_project_stale

    if organization_id:
        projects = (
            (
                await session.execute(
                    select(Project.id).where(Project.organization_id == organization_id)
                )
            )
            .scalars()
            .all()
        )
        for project_id in projects:
            await mark_project_stale(session, project_id)


async def mark_document_stale(session: AsyncSession, document: Document) -> None:
    from app.services.freshness import mark_project_stale

    if document.project_id:
        await mark_project_stale(session, document.project_id)
    else:
        await mark_organization_stale(session, document.organization_id)


def search_tokens(value: str) -> str:
    words = re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]", value.lower())
    chinese = re.findall(r"[\u3400-\u9fff]{2,}", value)
    words.extend(part[index : index + 2] for part in chinese for index in range(len(part) - 1))
    return " ".join(dict.fromkeys(words))


async def index_document(
    session: AsyncSession,
    document: Document,
    *,
    with_embeddings: bool,
    job_id: str | None = None,
    config_id: str | None = None,
) -> int:
    chunks = (
        (await session.execute(select(SearchChunk).where(SearchChunk.document_id == document.id)))
        .scalars()
        .all()
    )
    metadata = document.metadata_json or {}
    text_version = metadata.get("text_version", 0)
    if chunks and (
        any(chunk.revision_id != document.current_revision_id for chunk in chunks)
        or metadata.get("index_text_version", 0) != text_version
    ):
        await session.execute(delete(SearchChunk).where(SearchChunk.document_id == document.id))
        chunks = []
    if not chunks:
        blocks = (
            await session.execute(
                select(Block, Page)
                .join(Page, Page.id == Block.page_id)
                .where(
                    Page.revision_id == document.current_revision_id,
                    Block.kind != "historical_text",
                )
                .order_by(Page.page_index, Block.reading_order)
            )
        ).all()
        for block, page in blocks:
            if not block.text.strip():
                continue
            for start in range(0, len(block.text), 2200):
                content = block.text[start : start + 2400]
                span = (
                    await session.execute(
                        select(SourceSpan)
                        .where(
                            SourceSpan.block_id == block.id,
                            SourceSpan.char_start == start,
                            SourceSpan.char_end == start + len(content),
                            SourceSpan.quote_hash == sha256_text(content),
                            SourceSpan.table_cell_id.is_(None),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if span is None:
                    span = SourceSpan(
                        document_id=document.id,
                        revision_id=page.revision_id,
                        page_id=page.id,
                        block_id=block.id,
                        char_start=start,
                        char_end=start + len(content),
                        quote=content,
                        quote_hash=sha256_text(content),
                        bbox_json=[block.x0, block.y0, block.x1, block.y1],
                    )
                    session.add(span)
                    await session.flush()
                chunk = SearchChunk(
                    document_id=document.id,
                    revision_id=page.revision_id,
                    page_id=page.id,
                    source_span_id=span.id,
                    text=content,
                    tokens=search_tokens(content),
                )
                session.add(chunk)
                await session.flush()
                if session.bind.dialect.name == "sqlite":
                    await session.execute(
                        text("INSERT INTO search_chunks_fts(chunk_id,tokens) VALUES (:id,:tokens)"),
                        {"id": chunk.id, "tokens": chunk.tokens},
                    )
                chunks.append(chunk)
        document.metadata_json = {
            **document.metadata_json,
            "index_text_version": text_version,
        }
        await session.commit()
    if with_embeddings:
        signature, vectors = await embed_texts(
            session,
            [chunk.text for chunk in chunks],
            job_id=job_id,
            config_id=config_id,
        )
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding_id = vector.id
        document.metadata_json = {
            **document.metadata_json,
            "embedding_signature": signature,
        }
        await session.commit()
    return len(chunks)
