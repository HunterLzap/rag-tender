"""业绩项目库服务。"""

import json
import re
from datetime import datetime
from typing import Any, Optional

from app.database import get_db
from app.models.performance import PerformanceProject


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dump_file_ids(file_ids: list[int] | None) -> str:
    return json.dumps(file_ids or [], ensure_ascii=False)


def _load_file_ids(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [int(item) for item in parsed if isinstance(item, int) or str(item).isdigit()]


def _normalize_amount(value: str) -> str:
    amount = value.strip()
    if amount.lower().endswith("w"):
        return f"{amount[:-1]}万"
    if amount.endswith("万元") or amount.endswith("万"):
        return amount
    return amount


def _extract_year_from_filename(filename: str | None) -> Optional[str]:
    if not filename:
        return None
    match = re.search(r"(20\d{2})", filename)
    return match.group(1) if match else None


def _compact_ocr_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.match(r"^\d+\s+", line):
            if current:
                rows.append(" ".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        rows.append(" ".join(current))
    return rows


def parse_performance_projects_from_text(
    text: str,
    filename: str | None = None,
    file_id: int | None = None,
) -> list[dict[str, Any]]:
    """从年度业绩表 OCR 文本中本地拆出业绩项目，不依赖 LLM。"""
    normalized_text = re.sub(r"\s+", "", text or "")
    if not normalized_text or ("业绩" not in normalized_text and "业绩" not in (filename or "")):
        return []

    year = _extract_year_from_filename(filename)
    projects: list[dict[str, Any]] = []
    for row in _compact_ocr_lines(text):
        match = re.match(
            r"^\d+\s+(.+?有限公司)\s+(.+?)\s+([\u4e00-\u9fffA-Za-z]+)\s+(\d+(?:\.\d+)?\s*(?:W|w|万|万元))$",
            row,
        )
        if not match:
            continue

        client_name, middle, location, amount = match.groups()
        middle_parts = middle.split()
        if len(middle_parts) < 2:
            continue
        project_name = "".join(middle_parts[:-1])
        project_scope = middle_parts[-1]
        scope_with_location = f"{project_scope}；地点：{location}"
        project: dict[str, Any] = {
            "project_name": project_name,
            "client_name": client_name,
            "contract_no": None,
            "contract_amount": _normalize_amount(amount.replace(" ", "")),
            "sign_date": None,
            "completion_date": None,
            "project_scope": scope_with_location,
            "year": year,
            "file_ids": [file_id] if file_id is not None else [],
            "remark": "自动从年度业绩表解析",
        }
        projects.append(project)
    return projects


def _row_to_project(row: Any) -> PerformanceProject:
    data = dict(row)
    data["file_ids"] = _load_file_ids(data.get("file_ids"))
    return PerformanceProject(**data)


async def list_projects() -> list[PerformanceProject]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM performance_projects ORDER BY id DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_project(row) for row in rows]
    finally:
        await db.close()


async def get_project(project_id: int) -> Optional[PerformanceProject]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM performance_projects WHERE id = ?",
            (project_id,),
        )
        row = await cursor.fetchone()
        return _row_to_project(row) if row else None
    finally:
        await db.close()


async def create_project(data: dict[str, Any]) -> PerformanceProject:
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO performance_projects
               (project_name, client_name, contract_no, contract_amount, sign_date,
                completion_date, project_scope, year, file_ids, remark, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["project_name"],
                data.get("client_name"),
                data.get("contract_no"),
                data.get("contract_amount"),
                data.get("sign_date"),
                data.get("completion_date"),
                data.get("project_scope"),
                data.get("year"),
                _dump_file_ids(data.get("file_ids")),
                data.get("remark"),
                now,
                now,
            ),
        )
        await db.commit()
        project_id = cursor.lastrowid
    finally:
        await db.close()
    result = await get_project(project_id)
    assert result is not None
    return result


async def sync_projects_from_performance_file(
    file_id: int,
    filename: str,
    text: str,
) -> list[PerformanceProject]:
    """从业绩文件文本同步自动解析项目；不依赖 LLM。"""
    projects = parse_performance_projects_from_text(text, filename=filename, file_id=file_id)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, file_ids, remark FROM performance_projects WHERE remark = ?",
            ("自动从年度业绩表解析",),
        )
        rows = await cursor.fetchall()
        for row in rows:
            if file_id in _load_file_ids(row["file_ids"]):
                await db.execute("DELETE FROM performance_projects WHERE id = ?", (row["id"],))
        await db.commit()
    finally:
        await db.close()

    created: list[PerformanceProject] = []
    for project in projects:
        created.append(await create_project(project))
    return created


async def update_project(
    project_id: int,
    data: dict[str, Any],
) -> Optional[PerformanceProject]:
    allowed_fields = {
        "project_name",
        "client_name",
        "contract_no",
        "contract_amount",
        "sign_date",
        "completion_date",
        "project_scope",
        "year",
        "file_ids",
        "remark",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return await get_project(project_id)

    if "file_ids" in updates:
        updates["file_ids"] = _dump_file_ids(updates["file_ids"])
    updates["updated_at"] = _now_iso()

    db = await get_db()
    try:
        sets = [f"{key} = ?" for key in updates]
        params = list(updates.values())
        params.append(project_id)
        cursor = await db.execute(
            f"UPDATE performance_projects SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    finally:
        await db.close()
    return await get_project(project_id)


async def delete_project(project_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM performance_projects WHERE id = ?",
            (project_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
