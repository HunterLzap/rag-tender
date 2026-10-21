from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.document_ir import ParsedBlock, ParsedDocument
from app.models import (
    Block,
    Document,
    DocumentRevision,
    Page,
    ParagraphNode,
    ParseStatus,
    SourceSpan,
    TableCell,
)
from app.storage import sha256_text


def _block_quote(block: ParsedBlock) -> str:
    return block.text.strip()


async def persist_parsed_document(
    session: AsyncSession,
    document: Document,
    parsed: ParsedDocument,
    parser_version: str = "v2.0",
) -> DocumentRevision:
    current = await session.execute(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == document.id)
        .order_by(DocumentRevision.revision_no.desc())
        .limit(1)
    )
    latest = current.scalar_one_or_none()
    revision = DocumentRevision(
        document_id=document.id,
        revision_no=(latest.revision_no + 1) if latest else 1,
        parser_version=parser_version,
        parse_status=ParseStatus.COMPLETED,
        page_count=len(parsed.pages),
        metadata_json=parsed.metadata,
    )
    session.add(revision)
    await session.flush()

    for parsed_page in parsed.pages:
        page = Page(
            document_id=document.id,
            revision_id=revision.id,
            page_index=parsed_page.page_index,
            printed_label=parsed_page.printed_label,
            width=parsed_page.width,
            height=parsed_page.height,
            text=parsed_page.text,
            render_path=str(parsed_page.render_path) if parsed_page.render_path else None,
            parse_mode=parsed_page.parse_mode,
            quality_flags=list(parsed_page.quality_flags),
            native_locator=parsed_page.native_locator,
        )
        session.add(page)
        await session.flush()

        if parsed_page.parse_mode == "needs_vision" and parsed_page.render_path:
            page.quality_flags = [*page.quality_flags, "vision_pending"]

        for parsed_block in parsed_page.blocks:
            block = Block(
                page_id=page.id,
                kind=parsed_block.kind,
                reading_order=parsed_block.order,
                text=parsed_block.text,
                x0=parsed_block.bbox[0],
                y0=parsed_block.bbox[1],
                x1=parsed_block.bbox[2],
                y1=parsed_block.bbox[3],
                metadata_json=parsed_block.metadata,
            )
            session.add(block)
            await session.flush()

            cell_rows: list[tuple[Any, TableCell]] = []
            for parsed_cell in parsed_block.cells:
                cell = TableCell(
                    block_id=block.id,
                    row_index=parsed_cell.row,
                    col_index=parsed_cell.col,
                    row_span=parsed_cell.row_span,
                    col_span=parsed_cell.col_span,
                    text=parsed_cell.text,
                    x0=parsed_cell.bbox[0],
                    y0=parsed_cell.bbox[1],
                    x1=parsed_cell.bbox[2],
                    y1=parsed_cell.bbox[3],
                    native_locator=parsed_cell.native_locator,
                )
                session.add(cell)
                await session.flush()
                cell_rows.append((parsed_cell, cell))

            quote = _block_quote(parsed_block)
            if quote:
                bbox = parsed_block.bbox
                session.add(
                    SourceSpan(
                        document_id=document.id,
                        revision_id=revision.id,
                        page_id=page.id,
                        block_id=block.id,
                        char_start=0,
                        char_end=len(quote),
                        quote=quote,
                        quote_hash=sha256_text(quote),
                        bbox_json=[bbox[0], bbox[1], bbox[2], bbox[3]],
                    )
                )

            for parsed_cell, cell in cell_rows:
                quote = parsed_cell.text.strip()
                if not quote:
                    continue
                bbox = parsed_cell.bbox
                session.add(
                    SourceSpan(
                        document_id=document.id,
                        revision_id=revision.id,
                        page_id=page.id,
                        block_id=block.id,
                        table_cell_id=cell.id,
                        char_start=0,
                        char_end=len(quote),
                        quote=quote,
                        quote_hash=sha256_text(quote),
                        bbox_json=[bbox[0], bbox[1], bbox[2], bbox[3]],
                    )
                )

    document.current_revision_id = revision.id
    document.page_count = len(parsed.pages)
    document.metadata_json = {**(document.metadata_json or {}), **parsed.metadata}
    await session.flush()
    return revision


async def rebuild_section_tree(
    session: AsyncSession, revision_id: str
) -> list[ParagraphNode]:
    await session.execute(
        ParagraphNode.__table__.delete().where(ParagraphNode.revision_id == revision_id)
    )
    pages = (
        await session.execute(
            select(Page).where(Page.revision_id == revision_id).order_by(Page.page_index)
        )
    ).scalars()
    nodes: list[ParagraphNode] = []
    stack: list[ParagraphNode] = []
    for page in pages:
        blocks = (
            await session.execute(
                select(Block).where(Block.page_id == page.id).order_by(Block.reading_order)
            )
        ).scalars()
        for block in blocks:
            text = block.text.strip()
            if not text or len(text) > 120:
                continue
            level = _heading_level(text)
            if level is None:
                continue
            while stack and stack[-1].level >= level:
                stack.pop()
            path = "/".join([*[item.title or "" for item in stack], text])
            node = ParagraphNode(
                revision_id=revision_id,
                parent_id=stack[-1].id if stack else None,
                level=level,
                title=text,
                path=path,
                page_start=page.page_index,
                page_end=page.page_index,
                block_ids=[block.id],
            )
            session.add(node)
            await session.flush()
            stack.append(node)
            nodes.append(node)
    await session.flush()
    return nodes


def _heading_level(text: str) -> int | None:
    import re

    patterns = (
        (1, r"^[一二三四五六七八九十]+、"),
        (2, r"^\d+\.\d+\s*"),
        (3, r"^\d+\.\s*"),
    )
    for level, pattern in patterns:
        if re.match(pattern, text):
            return level
    return None
