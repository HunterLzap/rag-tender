import csv
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from docx import Document as DocxDocument
from openpyxl import load_workbook

from app.config import get_settings
from app.domain.document_ir import (
    DocumentNeedsVision,
    ParsedBlock,
    ParsedCell,
    ParsedDocument,
    ParsedPage,
)

TEXT_MIN_CHARS = 20


def _clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _words_to_lines(words: Iterable[dict]) -> list[dict]:
    lines: list[dict] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if not word.get("text"):
            continue
        top = word["top"]
        current = lines[-1] if lines else None
        if current and abs(current["top"] - top) <= 2.5:
            current["words"].append(word)
            current["x0"] = min(current["x0"], word["x0"])
            current["x1"] = max(current["x1"], word["x1"])
            current["bottom"] = max(current["bottom"], word["bottom"])
        else:
            lines.append(
                {
                    "top": top,
                    "x0": word["x0"],
                    "x1": word["x1"],
                    "bottom": word["bottom"],
                    "words": [word],
                }
            )
    for line in lines:
        line["text"] = " ".join(word["text"] for word in line["words"])
    return lines


def _render_pdf_page(pdf: pdfium.PdfDocument, page_index: int, output: Path) -> Path:
    settings = get_settings()
    output.parent.mkdir(parents=True, exist_ok=True)
    page = pdf[page_index]
    bitmap = page.render(scale=settings.render_scale)
    image = bitmap.to_pil()
    image.save(output, format="PNG")
    return output


def _parse_pdf(path: Path, render_dir: Path | None) -> ParsedDocument:
    pages: list[ParsedPage] = []
    pdfium_doc = pdfium.PdfDocument(path)
    try:
        with pdfplumber.open(path) as pdf:
            max_pages = get_settings().max_pdf_pages
            if len(pdf.pages) > max_pages:
                raise DocumentNeedsVision(f"PDF 页数超过上限 {max_pages}")
            for index, raw_page in enumerate(pdf.pages):
                text = _clean_text(raw_page.extract_text() or "")
                lines = _words_to_lines(raw_page.extract_words())
                blocks: list[ParsedBlock] = []
                order = 0
                for line in lines:
                    blocks.append(
                        ParsedBlock(
                            kind="line",
                            text=line["text"],
                            bbox=(line["x0"], line["top"], line["x1"], line["bottom"]),
                            order=order,
                        )
                    )
                    order += 1

                tables = raw_page.find_tables()
                for table_index, table in enumerate(tables):
                    extracted = table.extract()
                    if not extracted:
                        continue
                    cell_boxes = table.cells
                    cells: list[ParsedCell] = []
                    for row_index, row in enumerate(extracted):
                        for col_index, value in enumerate(row):
                            value = _clean_text(value or "")
                            if not value:
                                continue
                            flat_index = row_index * len(row) + col_index
                            bbox = (
                                cell_boxes[flat_index]
                                if flat_index < len(cell_boxes) and cell_boxes[flat_index]
                                else table.bbox
                            )
                            cells.append(
                                ParsedCell(
                                    row=row_index,
                                    col=col_index,
                                    row_span=1,
                                    col_span=1,
                                    text=value,
                                    bbox=tuple(float(v) for v in bbox),
                                    native_locator={
                                        "table_index": table_index,
                                        "row": row_index,
                                        "col": col_index,
                                    },
                                )
                            )
                    blocks.append(
                        ParsedBlock(
                            kind="table",
                            text="\n".join(
                                " | ".join(_clean_text(c or "") for c in row) for row in extracted
                            ),
                            bbox=tuple(float(v) for v in table.bbox),
                            order=order,
                            cells=tuple(cells),
                            metadata={"table_index": table_index},
                        )
                    )
                    if extracted:
                        table_top = float(table.bbox[1]) - 2
                        table_bottom = float(table.bbox[3]) + 2
                        line_blocks = [block for block in blocks if block.kind == "line"]
                        non_line_blocks = [block for block in blocks if block.kind != "line"]
                        line_blocks = [
                            block
                            for block in line_blocks
                            if not (
                                block.bbox[1] >= table_top - 2
                                and block.bbox[3] <= table_bottom + 2
                                and block.bbox[0] >= table.bbox[0] - 2
                                and block.bbox[2] <= table.bbox[2] + 2
                            )
                        ]
                        blocks = sorted(
                            [*non_line_blocks, *line_blocks],
                            key=lambda block: (block.bbox[1], block.bbox[0]),
                        )
                        for order_index, block in enumerate(blocks):
                            blocks[order_index] = ParsedBlock(
                                kind=block.kind,
                                text=block.text,
                                bbox=block.bbox,
                                order=order_index,
                                cells=block.cells,
                                metadata=block.metadata,
                            )
                        order = len(blocks)
                    order += 1

                render_path = None
                if render_dir is not None:
                    render_path = _render_pdf_page(
                        pdfium_doc, index, render_dir / f"page-{index + 1:04d}.png"
                    )
                mode = "text" if len(text) >= TEXT_MIN_CHARS else "needs_vision"
                pages.append(
                    ParsedPage(
                        page_index=index,
                        width=float(raw_page.width),
                        height=float(raw_page.height),
                        text=text,
                        blocks=tuple(blocks),
                        parse_mode=mode,
                        quality_flags=() if mode == "text" else ("no_text_layer",),
                        render_path=render_path,
                        native_locator={"kind": "pdf", "page_index": index},
                    )
                )
    finally:
        pdfium_doc.close()
    return ParsedDocument(pages=tuple(pages), metadata={"page_count": len(pages)})


def _docx_blocks(document: DocxDocument) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    order = 0
    for paragraph in document.paragraphs:
        text = _clean_text(paragraph.text)
        if not text:
            continue
        blocks.append(
            ParsedBlock(
                kind="paragraph",
                text=text,
                bbox=(0, 0, 595, 842),
                order=order,
                metadata={"style": paragraph.style.name if paragraph.style else None},
            )
        )
        order += 1
    for table_index, table in enumerate(document.tables):
        rows = [[_clean_text(cell.text) for cell in row.cells] for row in table.rows]
        cells = tuple(
            ParsedCell(
                row=row_index,
                col=col_index,
                row_span=1,
                col_span=1,
                text=value,
                bbox=(0, 0, 595, 842),
                native_locator={
                    "table_index": table_index,
                    "row": row_index,
                    "col": col_index,
                },
            )
            for row_index, row in enumerate(rows)
            for col_index, value in enumerate(row)
            if value
        )
        blocks.append(
            ParsedBlock(
                kind="table",
                text="\n".join(" | ".join(row) for row in rows),
                bbox=(0, 0, 595, 842),
                order=order,
                cells=cells,
                metadata={"table_index": table_index},
            )
        )
        order += 1
    return blocks


def _parse_docx(path: Path) -> ParsedDocument:
    _validate_zip(path)
    document = DocxDocument(path)
    blocks = _docx_blocks(document)
    return ParsedDocument(
        pages=(
            ParsedPage(
                page_index=0,
                width=595,
                height=842,
                text="\n\n".join(block.text for block in blocks),
                blocks=tuple(blocks),
                parse_mode="text",
                quality_flags=("no_page_coordinates",),
                native_locator={"kind": "docx"},
            ),
        ),
        metadata={"page_count": 1, "coordinate_quality": "document_flow"},
    )


def _parse_xlsx(path: Path) -> ParsedDocument:
    _validate_zip(path)
    workbook = load_workbook(path, data_only=True)
    pages: list[ParsedPage] = []
    for sheet_index, sheet in enumerate(workbook.worksheets):
        blocks: list[ParsedBlock] = []
        cells: list[ParsedCell] = []
        rows_text: list[str] = []
        for row_index, row in enumerate(sheet.iter_rows()):
            values = [str(cell.value).strip() if cell.value is not None else "" for cell in row]
            if any(values):
                rows_text.append(" | ".join(values))
            for col_index, value in enumerate(values):
                if not value:
                    continue
                cells.append(
                    ParsedCell(
                        row=row_index,
                        col=col_index,
                        row_span=1,
                        col_span=1,
                        text=value,
                        bbox=(col_index, row_index, col_index + 1, row_index + 1),
                        native_locator={
                            "sheet": sheet.title,
                            "row": row_index + 1,
                            "col": col_index + 1,
                        },
                    )
                )
        blocks.append(
            ParsedBlock(
                kind="table",
                text="\n".join(rows_text),
                bbox=(0, 0, max(sheet.max_column, 1), max(sheet.max_row, 1)),
                order=0,
                cells=tuple(cells),
                metadata={"sheet": sheet.title},
            )
        )
        pages.append(
            ParsedPage(
                page_index=sheet_index,
                width=max(sheet.max_column, 1),
                height=max(sheet.max_row, 1),
                text="\n".join(rows_text),
                blocks=tuple(blocks),
                printed_label=sheet.title,
                parse_mode="text",
                quality_flags=("spreadsheet_coordinates",),
                native_locator={"kind": "xlsx", "sheet": sheet.title},
            )
        )
    return ParsedDocument(pages=tuple(pages), metadata={"page_count": len(pages)})


def _parse_csv(path: Path) -> ParsedDocument:
    raw = path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(raw)))
    cells = tuple(
        ParsedCell(
            row=row_index,
            col=col_index,
            row_span=1,
            col_span=1,
            text=value,
            bbox=(col_index, row_index, col_index + 1, row_index + 1),
            native_locator={"row": row_index + 1, "col": col_index + 1},
        )
        for row_index, row in enumerate(rows)
        for col_index, value in enumerate(row)
        if value
    )
    block = ParsedBlock(
        kind="table",
        text="\n".join(" | ".join(row) for row in rows),
        bbox=(0, 0, max((len(row) for row in rows), default=1), max(len(rows), 1)),
        order=0,
        cells=cells,
    )
    page = ParsedPage(
        page_index=0,
        width=max((len(row) for row in rows), default=1),
        height=max(len(rows), 1),
        text=block.text,
        blocks=(block,),
        parse_mode="text",
        quality_flags=("spreadsheet_coordinates",),
        native_locator={"kind": "csv"},
    )
    return ParsedDocument(pages=(page,), metadata={"page_count": 1})


def _convert_to_pdf(path: Path) -> Path:
    soffice = get_settings().libreoffice_path or shutil.which("soffice")
    if not soffice:
        raise DocumentNeedsVision("未找到 LibreOffice，无法把 DOC 转换为 PDF")
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                temp_dir,
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        converted = Path(temp_dir) / f"{path.stem}.pdf"
        if result.returncode != 0 or not converted.exists():
            raise DocumentNeedsVision(f"LibreOffice 转换失败: {result.stderr[-500:]}")
        target = path.with_suffix(".converted.pdf")
        shutil.move(converted, target)
        return target


def parse_document(path: Path, render_root: Path | None = None) -> ParsedDocument:
    suffix = path.suffix.lower()
    render_dir = render_root / path.stem if render_root else None
    if suffix == ".pdf":
        return _parse_pdf(path, render_dir)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix == ".doc":
        return _parse_pdf(_convert_to_pdf(path), render_dir)
    if suffix == ".xlsx":
        return _parse_xlsx(path)
    if suffix == ".csv":
        return _parse_csv(path)
    raise DocumentNeedsVision(f"暂不支持直接解析 {suffix or '未知格式'} 文件")


def _validate_zip(path: Path) -> None:
    settings = get_settings()
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > settings.max_zip_entries:
                raise DocumentNeedsVision("Office 文件压缩条目过多")
            if sum(info.file_size for info in infos) > settings.max_zip_uncompressed_bytes:
                raise DocumentNeedsVision("Office 文件解压后过大")
    except zipfile.BadZipFile as exc:
        raise DocumentNeedsVision("Office 文件结构无效") from exc
