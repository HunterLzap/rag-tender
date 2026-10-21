from pathlib import Path

from app.services.parser import parse_document

SAMPLE = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"


def test_parse_pdf_preserves_pages_blocks_and_tables(tmp_path: Path):
    parsed = parse_document(SAMPLE, tmp_path)
    assert len(parsed.pages) == 11
    assert parsed.pages[0].parse_mode == "text"
    assert parsed.pages[0].blocks
    tables = [block for page in parsed.pages for block in page.blocks if block.kind == "table"]
    assert tables
    assert any("设备名称" in cell.text for table in tables for cell in table.cells)


def test_every_rendered_page_exists(tmp_path: Path):
    parsed = parse_document(SAMPLE, tmp_path)
    assert all(page.render_path and page.render_path.exists() for page in parsed.pages)


def test_table_cells_do_not_duplicate_table_text_as_lines(tmp_path: Path):
    parsed = parse_document(SAMPLE, tmp_path)
    page = parsed.pages[1]
    table = next(block for block in page.blocks if block.kind == "table")
    overlapping_lines = [
        block
        for block in page.blocks
        if block.kind == "line"
        and block.bbox[1] >= table.bbox[1] - 2
        and block.bbox[3] <= table.bbox[3] + 2
    ]
    assert overlapping_lines == []


def test_empty_cells_keep_exact_row_and_column_boxes(empty_table_pdf):
    parsed = parse_document(empty_table_pdf)
    table = next(block for block in parsed.pages[0].blocks if block.kind == "table")
    empty_cells = [cell for cell in table.cells if cell.text == ""]
    assert [(cell.row, cell.col) for cell in empty_cells] == [(1, 0), (1, 1), (1, 2)]
    assert [cell.bbox for cell in empty_cells] == [
        (50, 140, 220, 210),
        (220, 140, 450, 210),
        (450, 140, 550, 210),
    ]
