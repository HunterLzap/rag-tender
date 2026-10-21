"""Detect ruled scan tables without OCR or a model.

Morphological line extraction follows OpenCV's horizontal/vertical line method.
Enclosed grid regions preserve merged cells. Geometry is mapped back to the
unchanged source page after a temporary deskew used only for detection.
"""

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.domain.document_ir import ParsedBlock, ParsedCell


def _binary(gray: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12,
    )


def _deskew(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    height, width = gray.shape
    lines = cv2.HoughLinesP(
        _binary(gray), 1, np.pi / 1800,
        threshold=max(40, width // 14), minLineLength=max(60, width // 6),
        maxLineGap=max(8, width // 100),
    )
    angles = []
    if lines is not None:
        for x0, y0, x1, y1 in lines[:, 0]:
            angle = math.degrees(math.atan2(float(y1 - y0), float(x1 - x0)))
            if abs(angle) > 45:
                angle = angle - 90 if angle > 0 else angle + 90
            if abs(angle) <= 10:
                angles.append((angle, math.hypot(float(x1 - x0), float(y1 - y0))))
    angle = 0.0
    if angles:
        angles.sort()
        midpoint = sum(length for _, length in angles) / 2
        accumulated = 0.0
        for candidate, length in angles:
            accumulated += length
            if accumulated >= midpoint:
                angle = candidate
                break
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)
    deskewed = cv2.warpAffine(gray, matrix, (width, height), borderValue=255)
    return deskewed, cv2.invertAffineTransform(matrix), angle


def _cluster(values: list[float], tolerance: float) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def detect_scanned_tables(
    image_path: Path, page_width: float, page_height: float,
) -> list[ParsedBlock]:
    with Image.open(image_path) as image:
        gray = np.asarray(image.convert("L"))
    if gray.shape[1] > 1800:
        ratio = 1800 / gray.shape[1]
        gray = cv2.resize(gray, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA)
    height, width = gray.shape
    gray, inverse, angle = _deskew(gray)
    ink = _binary(gray)

    horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, width // 250), 1)),
    )
    horizontal = cv2.morphologyEx(
        horizontal, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(24, width // 35), 1)),
    )
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, height // 200))),
    )
    vertical = cv2.morphologyEx(
        vertical, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, height // 45))),
    )
    grid = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8))
    _, grid_labels = cv2.connectedComponents(grid)
    _, _, regions, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(grid), connectivity=4)
    groups: dict[int, list[tuple[int, int, int, int]]] = {}
    for x, y, cell_width, cell_height, area in regions[1:]:
        right, bottom = x + cell_width, y + cell_height
        if x == 0 or y == 0 or right >= width or bottom >= height:
            continue
        if cell_width < 14 or cell_height < 10:
            continue
        if area < cell_width * cell_height * 0.82:
            continue
        if cell_width * cell_height > width * height * 0.8:
            continue
        border = np.concatenate((
            grid_labels[y - 1, x:right], grid_labels[bottom, x:right],
            grid_labels[y:bottom, x - 1], grid_labels[y:bottom, right],
        ))
        labels = border[border > 0]
        if labels.size:
            parent = int(np.bincount(labels).argmax())
            groups.setdefault(parent, []).append((int(x), int(y), int(right), int(bottom)))

    def source_point(x: float, y: float) -> list[float]:
        result = inverse @ np.array([x, y, 1])
        return [
            max(0.0, min(page_width, float(result[0]) * page_width / width)),
            max(0.0, min(page_height, float(result[1]) * page_height / height)),
        ]

    results = []
    for boxes in sorted(groups.values(), key=lambda rows: min((box[1], box[0]) for box in rows)):
        if len(boxes) < 2:
            continue
        x_edges = _cluster([x for box in boxes for x in (box[0], box[2])], 7)
        y_edges = _cluster([y for box in boxes for y in (box[1], box[3])], 7)
        cells = []
        for left, top, right, bottom in boxes:
            col = min(range(len(x_edges)), key=lambda item: abs(x_edges[item] - left))
            end_col = min(range(len(x_edges)), key=lambda item: abs(x_edges[item] - right))
            row = min(range(len(y_edges)), key=lambda item: abs(y_edges[item] - top))
            end_row = min(range(len(y_edges)), key=lambda item: abs(y_edges[item] - bottom))
            if row >= end_row or col >= end_col:
                continue
            polygon = [
                source_point(x_edges[col], y_edges[row]),
                source_point(x_edges[end_col], y_edges[row]),
                source_point(x_edges[end_col], y_edges[end_row]),
                source_point(x_edges[col], y_edges[end_row]),
            ]
            crop = ink[top + 4:bottom - 4, left + 4:right - 4]
            has_ink = bool(crop.size and np.count_nonzero(crop) > max(8, crop.size * 0.004))
            cells.append(ParsedCell(
                row=row, col=col, row_span=end_row - row, col_span=end_col - col,
                text="",
                bbox=(
                    min(point[0] for point in polygon), min(point[1] for point in polygon),
                    max(point[0] for point in polygon), max(point[1] for point in polygon),
                ),
                native_locator={
                    "table_index": len(results), "row": row, "col": col,
                    "coordinate_quality": "scan_lines", "polygon": polygon,
                    "scan_has_content": has_ink, "scan_angle": round(angle, 3),
                },
            ))
        if len(cells) < 2:
            continue
        results.append(ParsedBlock(
            kind="table", text="",
            bbox=(
                min(cell.bbox[0] for cell in cells), min(cell.bbox[1] for cell in cells),
                max(cell.bbox[2] for cell in cells), max(cell.bbox[3] for cell in cells),
            ),
            order=len(results), cells=tuple(sorted(cells, key=lambda item: (item.row, item.col))),
            metadata={"table_index": len(results), "scan_detected": True, "scan_angle": angle},
        ))
    return results
