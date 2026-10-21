from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base


@pytest_asyncio.fixture
async def session(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("TENDER_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("TENDER_LIVE_MODEL_CALLS", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def empty_table_pdf(tmp_path: Path) -> Path:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(600, 400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    drawing = ["0.7 w"]
    for x in (50, 220, 450, 550):
        drawing.append(f"{x} 190 m {x} 300 l S")
    for y in (190, 260, 300):
        drawing.append(f"50 {y} m 550 {y} l S")
    for x, text in ((60, "Equipment"), (230, "Specification"), (460, "Quantity")):
        drawing.append(f"BT /F1 12 Tf {x} 275 Td ({text}) Tj ET")
    drawing.append("BT /F1 12 Tf 50 350 Td (Tender response template) Tj ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(drawing).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = tmp_path / "blank-table.pdf"
    with output.open("wb") as file:
        writer.write(file)
    return output
