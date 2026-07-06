"""检查报告导出服务。"""

from typing import Any

from app.database import get_db
from app.services.checker_service import CheckContext, run_checkers
from app.services.match_service import get_match_results
from app.services.submission_checklist_service import get_all as get_checklist


def _safe_filename(value: str | None) -> str:
    name = (value or "tender").strip() or "tender"
    for char in '\\/:*?"<>|':
        name = name.replace(char, "_")
    return name[:80]


async def _get_tender_summary(tender_id: int) -> dict[str, Any] | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, filename, title, region, procurement_type, budget, agency, status
               FROM tenders
               WHERE id = ?""",
            (tender_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def build_check_report(tender_id: int) -> dict[str, Any] | None:
    """构建结构化检查报告。"""
    tender = await _get_tender_summary(tender_id)
    if tender is None:
        return None

    matches = await get_match_results(tender_id)
    checklist = await get_checklist(tender_id)
    checker_results = await run_checkers(CheckContext(tender_id=tender_id))

    match_summary = {
        "matched": sum(1 for item in matches if item.status == "matched"),
        "unmatched": sum(1 for item in matches if item.status == "unmatched"),
        "needs_review": sum(1 for item in matches if item.status == "needs_review"),
        "total": len(matches),
    }
    red_flags = [item for item in checklist if "【红线】" in (item.remark or "")]
    missing_evidence: list[dict[str, Any]] = []
    for item in matches:
        gaps = [
            evidence.model_dump()
            for evidence in item.evidence_items
            if evidence.status in {"fail", "unknown"}
        ]
        if gaps:
            missing_evidence.append(
                {
                    "match_id": item.id,
                    "requirement_id": item.requirement_id,
                    "status": item.status,
                    "reason": item.reason,
                    "mismatch_detail": item.mismatch_detail,
                    "expected_qualification": item.expected_qualification,
                    "evidence_items": gaps,
                }
            )

    return {
        "tender": tender,
        "match_summary": match_summary,
        "unmatched": [item.model_dump() for item in matches if item.status == "unmatched"],
        "needs_review": [item.model_dump() for item in matches if item.status == "needs_review"],
        "missing_evidence": missing_evidence,
        "red_flags": [item.model_dump() for item in red_flags],
        "checkers": [
            {
                **result.__dict__,
                "evidence": [evidence.__dict__ for evidence in result.evidence],
            }
            for result in checker_results
        ],
    }


def render_check_report_markdown(report: dict[str, Any]) -> str:
    """将结构化检查报告渲染为 Markdown。"""
    tender = report["tender"]
    summary = report["match_summary"]
    lines = [
        f"# {tender.get('title') or tender.get('filename') or '标书'} 检查报告",
        "",
        "## 标书基本信息",
        f"- 文件：{tender.get('filename') or ''}",
        f"- 项目：{tender.get('title') or ''}",
        f"- 预算：{tender.get('budget') or '未识别'}",
        "",
        "## 资质匹配总览",
        f"- 总数：{summary['total']}",
        f"- 符合：{summary['matched']}",
        f"- 不符合：{summary['unmatched']}",
        f"- 待确认：{summary['needs_review']}",
        "",
        "## 不通过项",
    ]
    if report["unmatched"]:
        for item in report["unmatched"]:
            lines.append(f"- 要求 {item['requirement_id']}：{item.get('reason') or '未说明'}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 待确认项"])
    if report["needs_review"]:
        for item in report["needs_review"]:
            lines.append(f"- 要求 {item['requirement_id']}：{item.get('reason') or '未说明'}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 缺失证据"])
    if report["missing_evidence"]:
        for item in report["missing_evidence"]:
            lines.append(f"- 要求 {item['requirement_id']}：{item.get('mismatch_detail') or item.get('reason') or '证据不足'}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 红线待办"])
    if report["red_flags"]:
        for item in report["red_flags"]:
            lines.append(f"- [{item['status']}] {item['item_name']}：{item.get('remark') or ''}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 检查器结果"])
    for result in report["checkers"]:
        lines.append(f"- {result['name']}：{result['summary']}")
    return "\n".join(lines) + "\n"


async def export_check_report_markdown(tender_id: int) -> dict[str, str] | None:
    """导出 Markdown 检查报告内容。"""
    report = await build_check_report(tender_id)
    if report is None:
        return None
    title = report["tender"].get("title") or report["tender"].get("filename")
    return {
        "filename": f"{_safe_filename(title)}_check_report.md",
        "content_type": "text/markdown; charset=utf-8",
        "content": render_check_report_markdown(report),
    }
