from pathlib import Path

import pytest

from app.models import Document, DocumentRole, FillSlot, Project
from app.services.fill import detect_fill_slots
from app.services.ir_persistence import persist_parsed_document
from app.services.parser import parse_document

SAMPLE = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"


@pytest.mark.asyncio
async def test_detects_table_headers_as_fill_slots(session, tmp_path):
    project = Project(name="fill")
    session.add(project)
    await session.flush()
    document = Document(
        project_id=project.id,
        role=DocumentRole.TEMPLATE,
        filename="template.pdf",
        storage_path=str(SAMPLE),
        sha256="b" * 64,
        file_size=SAMPLE.stat().st_size,
    )
    session.add(document)
    await session.flush()
    parsed = parse_document(SAMPLE, tmp_path)
    await persist_parsed_document(session, document, parsed)
    slots = await detect_fill_slots(session, document)
    await session.commit()
    assert slots
    stored = (await session.execute(FillSlot.__table__.select())).all()
    assert len(stored) == len(slots)
    assert any(slot.label == "设备名称" for slot in slots)
