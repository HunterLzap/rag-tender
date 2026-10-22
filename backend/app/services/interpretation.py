"""Source-backed tender reading, built from the same clauses used by comparison."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, Decision, Document, Page, Requirement, SourceSpan
from app.schemas import SourceSpanRead
from app.services.requirement_versions import version_state

SECTIONS = {
    "overview": "项目概况", "timeline": "关键节点", "qualification": "资格条件",
    "scoring": "评分办法", "technical": "技术与采购需求", "contract": "商务与合同",
    "submission": "编制与递交", "risk": "否决与风险", "amendments": "补遗与答疑",
}


def _section(item) -> str:
    if item.get("evaluation_type") == "score" or item.get("obligation") == "scored":
        return "scoring"
    category = item.get("category")
    if category in {"qualification", "personnel", "performance", "financial"}:
        return "qualification"
    return {"technical": "technical", "commercial": "contract",
            "submission": "submission"}.get(category, "submission")


async def read_tender(session: AsyncSession, project_id: str) -> dict:
    documents = list((await session.execute(select(Document).where(
        Document.project_id == project_id, Document.role.in_(["tender", "addendum", "qa"]),
    ).order_by(Document.created_at, Document.id))).scalars())
    latest = (await session.execute(select(AnalysisRun).where(
        AnalysisRun.project_id == project_id,
    ).order_by(AnalysisRun.created_at.desc()).limit(1))).scalar_one_or_none()
    current = {(d.id, d.current_revision_id, d.metadata_json.get("text_version", 0))
               for d in documents}
    snapshot = {(d["document_id"], d["revision_id"], d.get("text_version", 0))
                for d in latest.input_snapshot if (
                    d.get("role") in {"tender", "addendum", "qa"}
                    or d["document_id"] in {x.id for x in documents}
                    or latest.model_snapshot.get("execution_mode") == "manual"
                )
                } if latest else set()
    # Partial/older runs cannot hide newly uploaded amendments or new clauses.
    use_run = bool(latest and latest.status not in {"draft", "running", "failed"}
                   and snapshot == current)
    requirements = list((await session.execute(select(Requirement).where(
        Requirement.run_id == latest.id,
    ).order_by(Requirement.created_at, Requirement.id))).scalars()) if use_run else []
    replaced, conflicts = version_state(requirements)
    decisions = {d.requirement_id: d for d in (await session.execute(select(Decision).where(
        Decision.run_id == latest.id,
    ))).scalars()} if use_run else {}
    sources = {span.id: (span, page) for span, page in (await session.execute(
        select(SourceSpan, Page).join(Page, Page.id == SourceSpan.page_id)
        .where(SourceSpan.document_id.in_([d.id for d in documents]))
    )).all()}
    by_document = {d.id: d for d in documents}
    sections = {key: [] for key in SECTIONS}
    pending = []
    notes = []
    if use_run and latest.model_snapshot.get("execution_mode") == "manual":
        notes.extend(latest.coverage_notes)
    represented_spans = {r.source_span_id for r in requirements}
    represented_fingerprints = {r.fingerprint for r in requirements}

    def add(entry, section, *, requirement=None):
        pair = sources.get(entry.get("source_span_id"))
        if pair is None:
            return
        span, page = pair
        document = by_document[span.document_id]
        if span.revision_id != document.current_revision_id:
            return
        state = "active"
        if requirement:
            state = "superseded" if requirement.id in replaced else (
                "rejected" if requirement.review_status == "rejected" else
                "conflict" if requirement.id in conflicts else "active"
            )
        decision = decisions.get(requirement.id) if requirement else None
        row = {
            "id": requirement.id if requirement else span.id,
            "title": entry["title"], "content": entry.get("content", entry.get("statement", "")),
            "filename": document.filename, "page_index": page.page_index,
            "role": document.role, "source_span": SourceSpanRead.model_validate(span).model_dump(),
            "requirement_id": requirement.id if requirement else None,
            "state": state, "decision_status": decision.status if decision else None,
            "decision_stale": decision.stale if decision else False,
        }
        sections[section].append(row)
        if document.role in {"addendum", "qa"} and section != "amendments":
            sections["amendments"].append(row)
        if entry.get("consequence") == "rejection" and state not in {"superseded", "rejected"}:
            sections["risk"].append(row)

    for document in documents:
        metadata = document.metadata_json
        fresh = (
            metadata.get("requirements_revision") == document.current_revision_id
            and metadata.get("requirements_text_version", 0) == metadata.get("text_version", 0)
        )
        if not fresh or metadata.get("ai_status") not in {"ready", "needs_review"}:
            pending.append({"filename": document.filename,
                            "status": metadata.get("ai_status", "pending")})
        if fresh:
            notes.extend(f"{document.filename}：{note}"
                         for note in metadata.get("requirement_notes", []))
            if not use_run or latest.model_snapshot.get("execution_mode") == "manual":
                for entry in metadata.get("extracted_requirements", []):
                    if (entry["source_span_id"] not in represented_spans
                            and entry["fingerprint"] not in represented_fingerprints):
                        add(entry, _section(entry))
            if (metadata.get("reading_revision") == document.current_revision_id
                    and metadata.get("reading_text_version", 0) == metadata.get("text_version", 0)):
                for entry in metadata.get("reading_items", []):
                    add(entry, entry["section"])
    for requirement in requirements:
        entry = {key: getattr(requirement, key) for key in (
            "title", "statement", "category", "evaluation_type", "obligation", "consequence",
            "source_span_id",
        )}
        add(entry, _section(entry), requirement=requirement)
    # Dates/budgets from different documents remain traceable; upload order isn't legal priority.
    for key in ("overview", "timeline", "contract"):
        groups = {}
        for row in sections[key]:
            if row["requirement_id"] is None:
                groups.setdefault(row["title"], []).append(row)
        for rows in groups.values():
            if len({row["content"] for row in rows}) > 1:
                for row in rows:
                    row["state"] = "conflict"
    return {
        "project_id": project_id, "run_id": latest.id if use_run else None,
        "document_count": len(documents),
        "coverage_notes": list(dict.fromkeys(notes)),
        "pending_documents": pending,
        "amendments_pending": bool(not use_run and any(d.role != "tender" for d in documents)),
        "sections": [{"key": key, "title": title, "items": sections[key]}
                     for key, title in SECTIONS.items()],
    }


def reading_markdown(reading: dict) -> str:
    lines = ["# 标书解读", ""]
    if reading["pending_documents"]:
        lines += ["部分资料尚未完成解读，以下内容需结合原文核对。", ""]
    if reading["amendments_pending"]:
        lines += ["补遗与原条款的适用关系尚待核对，请勿仅按上传顺序采用。", ""]
    if reading["coverage_notes"]:
        lines += ["## 解读范围待核对", "", *[f"- {n}" for n in reading["coverage_notes"]], ""]
    labels = {"superseded": "已替代", "rejected": "已否决", "conflict": "待确认"}
    for section in reading["sections"]:
        lines += [f"## {section['title']}", ""]
        for item in section["items"]:
            suffix = f"（{labels[item['state']]}）" if item["state"] in labels else ""
            lines += [f"### {item['title']}{suffix}", item["content"],
                      f"来源：{item['filename']} · 第 {item['page_index'] + 1} 页",
                      f"原文：{item['source_span']['quote']}", ""]
            if item["decision_status"]:
                label = "待重新核对" if item["decision_stale"] else {
                    "met": "符合", "not_met": "不符合", "needs_review": "待确认",
                    "not_applicable": "不适用",
                }[item["decision_status"]]
                lines += [f"对标结论：{label}", ""]
        if not section["items"]:
            lines += ["暂无已核实的条目，请对照原文补充。", ""]
    return "\n".join(lines)
