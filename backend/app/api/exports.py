import csv
import io
import re
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import get_report
from app.db import get_session
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    AnnotationAsset,
    Document,
    FillPlan,
    FillSuggestion,
    FillTarget,
    Page,
)

router = APIRouter()


def _filename(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n]', "_", value)[:120] or "投标模板"


@router.get("/analysis-runs/{run_id}/export")
async def export_bundle(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析记录不存在")
    if run.status in {AnalysisStatus.DRAFT, AnalysisStatus.RUNNING}:
        raise HTTPException(409, "请等待当前分析结束后再导出")
    report = await get_report(run_id, session)
    rows = (
        await session.execute(
            select(FillTarget, FillSuggestion, Document, Page)
            .join(FillPlan, FillPlan.id == FillTarget.plan_id)
            .join(Document, Document.id == FillPlan.document_id)
            .join(Page, Page.id == FillTarget.page_id)
            .outerjoin(FillSuggestion, FillSuggestion.target_id == FillTarget.id)
            .where(FillPlan.run_id == run_id)
            .order_by(Document.created_at, Page.page_index, FillTarget.created_at)
        )
    ).all()
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(["模板文件", "页码", "填写位置", "填写内容", "审阅状态", "说明", "填写依据"])
    labels = {
        "accepted": "已确认",
        "edited": "已修改",
        "proposed": "待确认",
        "rejected": "未采用",
        "missing_evidence": "待补充",
    }
    for target, suggestion, document, page in rows:
        writer.writerow(
            [
                document.filename,
                page.page_index + 1,
                target.label,
                suggestion.value or "" if suggestion else "",
                labels.get(suggestion.status, "待补充") if suggestion else "待补充",
                suggestion.rationale if suggestion else "",
                "；".join(
                    f"{ref.get('filename', '')} 第 {ref['page_index'] + 1} 页"
                    if ref.get("page_index") is not None
                    else ref.get("label", "原文来源")
                    for ref in (suggestion.source_refs if suggestion else [])
                ),
            ]
        )
    assets = (
        await session.execute(
            select(AnnotationAsset, Document, Page)
            .join(FillPlan, FillPlan.id == AnnotationAsset.plan_id)
            .join(Document, Document.id == FillPlan.document_id)
            .join(Page, Page.id == AnnotationAsset.page_id)
            .where(FillPlan.run_id == run_id)
            .order_by(Document.created_at, Page.page_index)
        )
    ).all()
    buffer = io.BytesIO()
    images = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (asset, document, page) in enumerate(assets, 1):
            source = Path(asset.path)
            if not source.exists():
                raise HTTPException(409, "标注图文件缺失，请在填写建议中更新后重试")
            filename = (
                f"标注图/{index:03d}-{_filename(document.filename)}-第{page.page_index + 1}页.png"
            )
            archive.write(source, filename)
            images.append(f"- [{document.filename} · 第 {page.page_index + 1} 页]({filename})")
        markdown = report.markdown
        if images:
            markdown += "\n\n## 原页标注图\n\n" + "\n".join(images)
        archive.writestr("投标准备检查报告.md", markdown.encode("utf-8"))
        archive.writestr("填写内容清单.csv", text.getvalue().encode("utf-8-sig"))
        archive.writestr(
            "使用说明.txt",
            "报告保留当前结论、人工复核和未完成事项。\n"
            "填写清单与标注图用于人工填写参考；原始投标文件未被自动改写。\n"
            "待补充、未采用和待重新核对的内容，请在正式提交前处理。\n",
        )
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote('投标准备资料.zip')}"
        },
    )
