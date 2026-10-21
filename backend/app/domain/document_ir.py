from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParsedCell:
    row: int
    col: int
    row_span: int
    col_span: int
    text: str
    bbox: tuple[float, float, float, float]
    native_locator: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedBlock:
    kind: str
    text: str
    bbox: tuple[float, float, float, float]
    order: int
    cells: tuple[ParsedCell, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedPage:
    page_index: int
    width: float
    height: float
    text: str
    blocks: tuple[ParsedBlock, ...]
    printed_label: str | None = None
    parse_mode: str = "text"
    quality_flags: tuple[str, ...] = ()
    render_path: Path | None = None
    native_locator: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    pages: tuple[ParsedPage, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParseError(RuntimeError):
    pass


class DocumentNeedsVision(DocumentParseError):
    pass
