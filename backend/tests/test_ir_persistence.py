from pathlib import Path

import pytest

from app.models import Document, DocumentRole, Page, Project
from app.services.ir_persistence import persist_parsed_document, rebuild_section_tree
from app.services.parser import parse_document

SAMPLE = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"


@pytest.mark.asyncio
async def test_persist_document_ir(session, tmp_path):
    project = Project(name="test")
    session.add(project)
    await session.flush()
    document = Document(
        project_id=project.id,
        role=DocumentRole.TENDER,
        filename="sample.pdf",
        storage_path=str(SAMPLE),
        sha256="a" * 64,
        file_size=SAMPLE.stat().st_size,
    )
    session.add(document)
    await session.flush()
    parsed = parse_document(SAMPLE, tmp_path)
    revision = await persist_parsed_document(session, document, parsed)
    nodes = await rebuild_section_tree(session, revision.id)
    await session.commit()
    pages = await session.execute(
        Page.__table__.select().where(Page.revision_id == revision.id)
    )
    assert len(pages.all()) == len(parsed.pages)
    assert nodes
    assert document.current_revision_id == revision.id
