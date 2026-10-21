from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import get_session
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    AnnotationAsset,
    Bid,
    Block,
    ChecklistItem,
    Decision,
    DecisionStatus,
    Document,
    DocumentRole,
    EvidenceFact,
    EvidenceItem,
    FillPlan,
    FillSuggestion,
    FillTarget,
    Job,
    ModelConfig,
    Organization,
    Page,
    Project,
    Requirement,
    ResponseValue,
    ReviewRecord,
    SourceSpan,
    SuggestionStatus,
)
from app.schemas import (
    AnalysisRunCreate,
    AnalysisRunRead,
    AnnotationAssetRead,
    BidCreate,
    BidRead,
    BidUpdate,
    BlockRead,
    ChecklistRead,
    ChecklistUpdate,
    DecisionRead,
    DocumentRead,
    EvidenceCreate,
    EvidenceRead,
    EvidenceUpdate,
    FillPlanRead,
    FillPlanRebuild,
    FillSlotRead,
    FillSuggestionRead,
    FillSuggestionUpdate,
    FillTargetRead,
    JobRead,
    ModelConfigCreate,
    ModelConfigRead,
    ModelTestRequest,
    ModelTestResult,
    PageDetail,
    PageRead,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ReportRead,
    RequirementRead,
    RequirementUpdate,
    ResponseValueCreate,
    ResponseValueRead,
    ResponseValueUpdate,
    ReviewCreate,
    ReviewRecordRead,
    SourceSpanRead,
)
from app.security import decrypt_secret, encrypt_secret, mask_secret
from app.services.analysis import enrich_evidence_facts
from app.services.checklist import build_checklist, mark_run_complete_if_ready
from app.services.fill import (
    create_fill_plan,
    detect_fill_slots,
    rebuild_fill_plan,
    render_annotations,
)
from app.services.freshness import mark_project_stale
from app.services.jobs import enqueue, request_cancel
from app.services.library import evidence_scope, mark_organization_stale
from app.services.model_gateway import test_model
from app.storage import store_upload

router = APIRouter()


def _page_document_filename(span: SourceSpan, document: Document | None) -> str | None:
    return document.filename if document else None


def _document_read(document: Document, *, evidence_count: int | None = None) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        project_id=document.project_id,
        organization_id=document.organization_id,
        role=document.role,
        filename=document.filename,
        content_type=document.content_type,
        sha256=document.sha256,
        file_size=document.file_size,
        page_count=document.page_count,
        current_revision_id=document.current_revision_id,
        current_page_count=document.page_count,
        parse_status=(document.metadata_json or {}).get("parse_status")
        or (
            "needs_review"
            if (document.metadata_json or {}).get("pages_needing_review")
            else "completed"
            if document.current_revision_id
            else "pending"
        ),
        parse_error=(document.metadata_json or {}).get("parse_error"),
        ai_status=(document.metadata_json or {}).get("ai_status", "pending"),
        ai_error=(document.metadata_json or {}).get("ai_error"),
        evidence_count=evidence_count
        if evidence_count is not None
        else (document.metadata_json or {}).get("evidence_count", 0),
        supersedes_id=document.supersedes_id,
        created_at=document.created_at,
    )


async def _read_documents(session: AsyncSession, documents) -> list[DocumentRead]:
    counts = dict(
        (
            await session.execute(
                select(SourceSpan.document_id, func.count(EvidenceItem.id))
                .join(EvidenceItem, EvidenceItem.source_span_id == SourceSpan.id)
                .join(Document, Document.id == SourceSpan.document_id)
                .where(
                    Document.id.in_([item.id for item in documents]),
                    SourceSpan.revision_id == Document.current_revision_id,
                    EvidenceItem.status != "archived",
                )
                .group_by(SourceSpan.document_id)
            )
        ).all()
    )
    return [_document_read(item, evidence_count=counts.get(item.id, 0)) for item in documents]


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tender-workbench",
        "version": "2.0.0",
        "live_model_calls": get_settings().live_model_calls,
    }


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)):
    projects = (
        (await session.execute(select(Project).order_by(Project.updated_at.desc()))).scalars().all()
    )
    result: list[ProjectRead] = []
    for project in projects:
        document_count = (
            await session.execute(
                select(func.count(Document.id)).where(Document.project_id == project.id)
            )
        ).scalar_one()
        latest_run = (
            await session.execute(
                select(AnalysisRun)
                .where(AnalysisRun.project_id == project.id)
                .order_by(AnalysisRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        result.append(
            ProjectRead(
                **project.__dict__,
                document_count=document_count,
                latest_run_id=latest_run.id if latest_run else None,
                latest_run_status=latest_run.status.value if latest_run else None,
            )
        )
    return result


@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectCreate, session: AsyncSession = Depends(get_session)):
    if payload.organization_id and await session.get(Organization, payload.organization_id) is None:
        raise HTTPException(400, "企业不存在")
    project = Project(**payload.model_dump())
    session.add(project)
    await session.commit()
    return ProjectRead(**project.__dict__)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return ProjectRead(**project.__dict__)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str, payload: ProjectUpdate, session: AsyncSession = Depends(get_session)
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    data = payload.model_dump(exclude_unset=True)
    if (
        data.get("organization_id")
        and await session.get(Organization, data["organization_id"]) is None
    ):
        raise HTTPException(400, "企业不存在")
    if any(
        key in data and data[key] != getattr(project, key)
        for key in (
            "bid_deadline",
            "organization_id",
            "bidder_name",
        )
    ):
        await mark_project_stale(session, project_id)
    for key, value in data.items():
        setattr(project, key, value)
    await session.flush()
    if project.auto_analyze and project.status == "active":
        from app.services.pipeline import schedule_analysis

        await schedule_analysis(session, project, automatic=True)
    await session.commit()
    return ProjectRead(**project.__dict__)


@router.get("/projects/{project_id}/bids", response_model=list[BidRead])
async def list_bids(project_id: str, session: AsyncSession = Depends(get_session)):
    return (
        (
            await session.execute(
                select(Bid).where(Bid.project_id == project_id).order_by(Bid.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/projects/{project_id}/bids", response_model=BidRead, status_code=201)
async def create_bid(
    project_id: str,
    payload: BidCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    bid = Bid(project_id=project_id, **payload.model_dump())
    session.add(bid)
    await session.flush()
    if bid.bid_deadline and project.bid_deadline is None:
        project.bid_deadline = bid.bid_deadline
    await session.commit()
    return bid


@router.patch("/bids/{bid_id}", response_model=BidRead)
async def update_bid(
    bid_id: str,
    payload: BidUpdate,
    session: AsyncSession = Depends(get_session),
):
    bid = await session.get(Bid, bid_id)
    if bid is None:
        raise HTTPException(404, "标段不存在")
    data = payload.model_dump(exclude_unset=True)
    if any(
        key in data and data[key] != getattr(bid, key)
        for key in ("bid_deadline", "as_of_date", "bidder_name")
    ):
        await mark_project_stale(session, bid.project_id)
    for key, value in data.items():
        setattr(bid, key, value)
    project = await session.get(Project, bid.project_id)
    if project is not None and "bid_deadline" in data:
        project.bid_deadline = data["bid_deadline"]
    await session.commit()
    return bid


@router.post("/projects/{project_id}/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    project_id: str,
    role: DocumentRole = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    if Path(file.filename or "").suffix.lower() not in {".pdf", ".doc", ".docx", ".xlsx", ".csv"}:
        raise HTTPException(400, "请选择 PDF、DOC、DOCX、XLSX 或 CSV 文件")
    content = await file.read()
    if not content:
        raise HTTPException(400, "文件为空，请选择有内容的文件")
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "文件超过上传大小限制")
    stored = store_upload(file.filename or "document.bin", content)
    duplicate = (
        await session.execute(
            select(Document.id).where(
                Document.project_id == project_id,
                Document.sha256 == stored.sha256,
                Document.role == role,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(409, "该文件已按相同用途上传，无需重复上传")
    document = Document(
        project_id=project_id,
        role=role,
        filename=file.filename or stored.path.name,
        content_type=file.content_type,
        storage_path=str(stored.path),
        sha256=stored.sha256,
        file_size=stored.size,
    )
    session.add(document)
    if role in {DocumentRole.TENDER, DocumentRole.ADDENDUM, DocumentRole.QA}:
        await mark_project_stale(session, project_id)
    await session.flush()
    await enqueue(
        session,
        "parse_document",
        {"document_id": document.id, "_dedupe_key": f"parse:{document.id}"},
    )
    await session.commit()
    return _document_read(document)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
async def list_documents(project_id: str, session: AsyncSession = Depends(get_session)):
    documents = (
        (
            await session.execute(
                select(Document)
                .where(Document.project_id == project_id)
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return await _read_documents(session, documents)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文档不存在")
    return (await _read_documents(session, [document]))[0]


@router.get("/documents/{document_id}/pages", response_model=list[PageRead])
async def list_pages(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None or not document.current_revision_id:
        return []
    pages = (
        (
            await session.execute(
                select(Page)
                .where(Page.revision_id == document.current_revision_id)
                .order_by(Page.page_index)
            )
        )
        .scalars()
        .all()
    )
    return pages


@router.get("/pages/{page_id}", response_model=PageDetail)
async def get_page(page_id: str, session: AsyncSession = Depends(get_session)):
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(404, "页面不存在")
    blocks = (
        (
            await session.execute(
                select(Block)
                .options(selectinload(Block.cells))
                .where(Block.page_id == page_id)
                .order_by(Block.reading_order)
            )
        )
        .scalars()
        .all()
    )
    detail = PageDetail(**page.__dict__)
    detail.blocks = [BlockRead(**block.__dict__) for block in blocks]
    return detail


@router.get("/pages/{page_id}/image")
async def get_page_image(page_id: str, session: AsyncSession = Depends(get_session)):
    page = await session.get(Page, page_id)
    if page is None or not page.render_path or not Path(page.render_path).exists():
        raise HTTPException(404, "页面图片不存在")
    return FileResponse(page.render_path, media_type="image/png")


@router.post(
    "/projects/{project_id}/analysis-runs",
    response_model=AnalysisRunRead,
    status_code=201,
)
async def create_analysis_run(
    project_id: str,
    payload: AnalysisRunCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    documents = (
        (
            await session.execute(
                select(Document).where(
                    Document.project_id == project_id,
                    Document.role.in_(
                        [DocumentRole.TENDER, DocumentRole.ADDENDUM, DocumentRole.QA]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not documents or any(not document.current_revision_id for document in documents):
        raise HTTPException(400, "请先完成全部招标、补遗和答疑文件的解析")
    if payload.mode == "manual":
        run = AnalysisRun(
            project_id=project_id,
            status=AnalysisStatus.NEEDS_REVIEW,
            stage="manual_review",
            progress=100,
            input_snapshot=[
                {
                    "document_id": document.id,
                    "revision_id": document.current_revision_id,
                    "text_version": (document.metadata_json or {}).get("text_version", 0),
                }
                for document in documents
            ],
            model_snapshot={"execution_mode": "manual"},
            coverage_notes=["人工工作台未执行模型提取，请对照原文核验要求是否完整"],
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        await build_checklist(session, run.id)
        await session.commit()
        return AnalysisRunRead(**run.__dict__)
    from app.services.model_gateway import ModelGatewayError
    from app.services.pipeline import schedule_analysis

    try:
        scheduled = await schedule_analysis(
            session,
            project,
            config_id=payload.model_config_id,
            prompt_version=payload.prompt_version,
            ruleset_version=payload.ruleset_version,
        )
    except ModelGatewayError as exc:
        raise HTTPException(409, str(exc)) from exc
    run, job = scheduled
    await session.commit()
    return AnalysisRunRead(**run.__dict__, job_id=job.id)


@router.get("/projects/{project_id}/analysis-runs", response_model=list[AnalysisRunRead])
async def list_runs(project_id: str, session: AsyncSession = Depends(get_session)):
    runs = (
        (
            await session.execute(
                select(AnalysisRun)
                .where(AnalysisRun.project_id == project_id)
                .order_by(AnalysisRun.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    result = []
    for run in runs:
        count = (
            await session.execute(
                select(func.count(Requirement.id)).where(Requirement.run_id == run.id)
            )
        ).scalar_one()
        result.append(AnalysisRunRead(**run.__dict__, requirement_count=count))
    return result


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunRead)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析任务不存在")
    count = (
        await session.execute(
            select(func.count(Requirement.id)).where(Requirement.run_id == run.id)
        )
    ).scalar_one()
    return AnalysisRunRead(**run.__dict__, requirement_count=count)


@router.get("/analysis-runs/{run_id}/requirements", response_model=list[RequirementRead])
async def list_requirements(run_id: str, session: AsyncSession = Depends(get_session)):
    rows = (
        (
            await session.execute(
                select(Requirement)
                .join(SourceSpan, SourceSpan.id == Requirement.source_span_id)
                .options(selectinload(Requirement.source_span))
                .where(Requirement.run_id == run_id)
                .order_by(Requirement.created_at)
            )
        )
        .scalars()
        .all()
    )
    result = []
    for requirement in rows:
        document = await session.get(Document, requirement.source_span.document_id)
        page = await session.get(Page, requirement.source_span.page_id)
        span = SourceSpanRead(
            **requirement.source_span.__dict__,
            document_filename=document.filename if document else None,
            page_index=page.page_index if page else None,
        )
        item = RequirementRead(**requirement.__dict__)
        item.source_span = span
        result.append(item)
    return result


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
async def update_requirement(
    requirement_id: str,
    payload: RequirementUpdate,
    session: AsyncSession = Depends(get_session),
):
    requirement = await session.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(404, "要求不存在")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(requirement, key, value)
    if "statement" in data and "condition_json" not in data:
        from app.domain.rules import extract_condition

        requirement.condition_json = extract_condition(requirement.statement, requirement.category)
    decision = (
        await session.execute(
            select(Decision).where(
                Decision.run_id == requirement.run_id,
                Decision.requirement_id == requirement.id,
            )
        )
    ).scalar_one_or_none()
    if decision is not None:
        decision.stale = True
        decision.status = DecisionStatus.NEEDS_REVIEW
        decision.summary = "要求已人工调整，请重新核对并保存复核结论"
    run = await session.get(AnalysisRun, requirement.run_id)
    if run and run.status == AnalysisStatus.COMPLETED:
        run.status = AnalysisStatus.NEEDS_REVIEW
    await build_checklist(session, requirement.run_id, reset_requirement_ids={requirement.id})
    await session.commit()
    return (
        await session.execute(
            select(Requirement)
            .options(selectinload(Requirement.source_span))
            .where(Requirement.id == requirement_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


@router.get("/analysis-runs/{run_id}/decisions", response_model=list[DecisionRead])
async def list_decisions(run_id: str, session: AsyncSession = Depends(get_session)):
    decisions = (
        (
            await session.execute(
                select(Decision)
                .options(selectinload(Decision.requirement).selectinload(Requirement.source_span))
                .options(selectinload(Decision.reviews))
                .where(Decision.run_id == run_id)
                .order_by(Decision.created_at)
            )
        )
        .scalars()
        .all()
    )
    return decisions


@router.post("/decisions/{decision_id}/reviews", response_model=ReviewRecordRead, status_code=201)
async def create_review(
    decision_id: str,
    payload: ReviewCreate,
    session: AsyncSession = Depends(get_session),
):
    decision = await session.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "判定不存在")
    if payload.evidence_ids is not None:
        run = await session.get(AnalysisRun, decision.run_id)
        project = await session.get(Project, run.project_id)
        evidence_ids = set(payload.evidence_ids)
        allowed = set(
            (
                await session.execute(
                    select(EvidenceItem.id).where(
                        evidence_scope(project),
                        EvidenceItem.id.in_(evidence_ids),
                    )
                )
            ).scalars()
        )
        if allowed != evidence_ids:
            raise HTTPException(400, "请选择当前项目的证据资料")
        decision.evidence_ids = list(dict.fromkeys(payload.evidence_ids))
    previous = decision.status.value
    decision.status = payload.new_status
    decision.stale = False
    decision.summary = payload.reason
    review = ReviewRecord(
        decision_id=decision.id,
        reviewer=payload.reviewer,
        previous_status=previous,
        new_status=payload.new_status,
        reason=payload.reason,
        evidence_snapshot=decision.evidence_ids,
    )
    session.add(review)
    await session.flush()
    await build_checklist(session, decision.run_id, reset_requirement_ids={decision.requirement_id})
    await mark_run_complete_if_ready(session, decision.run_id)
    await session.commit()
    return review


@router.get("/projects/{project_id}/evidence", response_model=list[EvidenceRead])
async def list_evidence(project_id: str, session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    evidence = (
        (
            await session.execute(
                select(EvidenceItem)
                .options(selectinload(EvidenceItem.facts).selectinload(EvidenceFact.source_span))
                .options(selectinload(EvidenceItem.source_span))
                .join(SourceSpan, SourceSpan.id == EvidenceItem.source_span_id)
                .join(Document, Document.id == SourceSpan.document_id)
                .where(
                    evidence_scope(project),
                    SourceSpan.revision_id == Document.current_revision_id,
                    EvidenceItem.status != "archived",
                )
                .order_by(EvidenceItem.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return evidence


@router.post("/projects/{project_id}/evidence", response_model=EvidenceRead, status_code=201)
async def create_evidence(
    project_id: str,
    payload: EvidenceCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    span = await session.get(SourceSpan, payload.source_span_id) if payload.source_span_id else None
    if span is None:
        raise HTTPException(400, "证据必须绑定一个有效来源片段")
    source_document = await session.get(Document, span.document_id)
    if source_document is None or not (
        source_document.project_id == project_id
        or (project.organization_id and source_document.organization_id == project.organization_id)
    ):
        raise HTTPException(400, "请选择当前项目或所属企业的证明材料来源")
    fingerprint = (
        __import__("hashlib")
        .sha256(f"{payload.kind}|{payload.title}|{payload.identifier or ''}".encode())
        .hexdigest()
    )
    evidence = EvidenceItem(
        project_id=None if source_document.organization_id else project_id,
        organization_id=source_document.organization_id,
        kind=payload.kind,
        title=payload.title,
        holder=payload.holder,
        issuer=payload.issuer,
        identifier=payload.identifier,
        issued_on=payload.issued_on,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        payload=payload.payload,
        source_span_id=span.id,
        fingerprint=fingerprint,
    )
    session.add(evidence)
    await session.flush()
    for fact in payload.facts:
        session.add(
            EvidenceFact(
                evidence_id=evidence.id,
                **fact.model_dump(),
            )
        )
    await enrich_evidence_facts(session, evidence, payload.payload)
    if evidence.organization_id:
        await mark_organization_stale(session, evidence.organization_id)
    else:
        await mark_project_stale(session, project_id)
    await session.commit()
    return await _load_evidence(session, evidence.id)


@router.patch("/evidence/{evidence_id}", response_model=EvidenceRead)
async def update_evidence(
    evidence_id: str,
    payload: EvidenceUpdate,
    session: AsyncSession = Depends(get_session),
):
    evidence = await session.get(EvidenceItem, evidence_id)
    if evidence is None:
        raise HTTPException(404, "证据不存在")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(evidence, key, value)
    if "payload" in data:
        await session.execute(delete(EvidenceFact).where(EvidenceFact.evidence_id == evidence_id))
        await enrich_evidence_facts(session, evidence, evidence.payload)
    else:
        facts = (
            (
                await session.execute(
                    select(EvidenceFact).where(EvidenceFact.evidence_id == evidence_id)
                )
            )
            .scalars()
            .all()
        )
        for fact in facts:
            if "review_status" in data:
                fact.review_status = evidence.review_status
            if "holder" in data:
                fact.holder = evidence.holder
            if "valid_until" in data and fact.fact_key in {"valid_until", "expiry_date"}:
                fact.value_date = evidence.valid_until
    if evidence.organization_id:
        await mark_organization_stale(session, evidence.organization_id)
    else:
        await mark_project_stale(session, evidence.project_id)
    from app.services.pipeline import schedule_related_projects

    await schedule_related_projects(session, evidence)
    await session.commit()
    return await _load_evidence(session, evidence.id)


async def _load_evidence(session: AsyncSession, evidence_id: str) -> EvidenceItem:
    return (
        await session.execute(
            select(EvidenceItem)
            .options(selectinload(EvidenceItem.facts).selectinload(EvidenceFact.source_span))
            .options(selectinload(EvidenceItem.source_span))
            .where(EvidenceItem.id == evidence_id)
        )
    ).scalar_one()


@router.get("/projects/{project_id}/response-values", response_model=list[ResponseValueRead])
async def list_response_values(project_id: str, session: AsyncSession = Depends(get_session)):
    return (
        (
            await session.execute(
                select(ResponseValue)
                .where(ResponseValue.project_id == project_id)
                .order_by(ResponseValue.label)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/projects/{project_id}/response-values",
    response_model=ResponseValueRead,
    status_code=201,
)
async def create_response_value(
    project_id: str,
    payload: ResponseValueCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    if payload.bid_id and await session.get(Bid, payload.bid_id) is None:
        raise HTTPException(400, "标段不存在")
    exists = (
        await session.execute(
            select(ResponseValue).where(
                ResponseValue.project_id == project_id,
                ResponseValue.key == payload.key,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "响应值键已存在，请编辑已有记录")
    value = ResponseValue(project_id=project_id, **payload.model_dump())
    session.add(value)
    await mark_project_stale(session, project_id)
    from app.services.pipeline import schedule_analysis

    if project.auto_analyze and project.status == "active":
        await schedule_analysis(session, project, automatic=True)
    await session.commit()
    return value


@router.patch("/response-values/{value_id}", response_model=ResponseValueRead)
async def update_response_value(
    value_id: str,
    payload: ResponseValueUpdate,
    session: AsyncSession = Depends(get_session),
):
    value = await session.get(ResponseValue, value_id)
    if value is None:
        raise HTTPException(404, "响应值不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("bid_id") and await session.get(Bid, data["bid_id"]) is None:
        raise HTTPException(400, "标段不存在")
    for key, field in data.items():
        setattr(value, key, field)
    value.version += 1
    await mark_project_stale(session, value.project_id)
    project = await session.get(Project, value.project_id)
    from app.services.pipeline import schedule_analysis

    if project.auto_analyze and project.status == "active":
        await schedule_analysis(session, project, automatic=True)
    await session.commit()
    return value


@router.delete("/response-values/{value_id}", status_code=204)
async def delete_response_value(value_id: str, session: AsyncSession = Depends(get_session)):
    value = await session.get(ResponseValue, value_id)
    if value is None:
        raise HTTPException(404, "响应值不存在")
    project = await session.get(Project, value.project_id)
    await mark_project_stale(session, value.project_id)
    await session.delete(value)
    from app.services.pipeline import schedule_analysis

    if project.auto_analyze and project.status == "active":
        await schedule_analysis(session, project, automatic=True)
    await session.commit()


@router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    return job


@router.get("/projects/{project_id}/jobs", response_model=list[JobRead])
async def list_jobs(project_id: str, session: AsyncSession = Depends(get_session)):
    jobs = (
        (
            await session.execute(
                select(Job)
                .where(Job.payload["project_id"].as_string() == project_id)
                .order_by(Job.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return jobs


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await request_cancel(session, job_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/model-configs", response_model=ModelConfigRead, status_code=201)
async def create_model_config(
    payload: ModelConfigCreate, session: AsyncSession = Depends(get_session)
):
    if payload.is_active:
        await session.execute(update(ModelConfig).values(is_active=False))
    config = ModelConfig(
        name=payload.name,
        provider=payload.provider,
        base_url=payload.base_url,
        api_key_encrypted=encrypt_secret(payload.api_key),
        text_model=payload.text_model,
        vision_model=payload.vision_model,
        embedding_model=payload.embedding_model,
        embedding_base_url=payload.embedding_base_url,
        embedding_api_key_encrypted=encrypt_secret(payload.embedding_api_key)
        if payload.embedding_api_key
        else None,
        embedding_dimensions=payload.embedding_dimensions,
        is_active=payload.is_active,
        config_json=payload.config_json,
    )
    session.add(config)
    await session.commit()
    from app.services.pipeline import resume_pending_documents

    await resume_pending_documents(session)
    return _model_config_read(config, payload.api_key)


@router.get("/model-configs", response_model=list[ModelConfigRead])
async def list_model_configs(session: AsyncSession = Depends(get_session)):
    configs = (
        (await session.execute(select(ModelConfig).order_by(ModelConfig.updated_at.desc())))
        .scalars()
        .all()
    )
    return [_model_config_read(config, "") for config in configs]


@router.post("/model-configs/test", response_model=ModelTestResult)
async def test_config(
    payload: ModelTestRequest,
    session: AsyncSession = Depends(get_session),
):
    base_url = payload.base_url
    api_key = payload.api_key
    model = payload.model
    if payload.config_id:
        config = await session.get(ModelConfig, payload.config_id)
        if config is None:
            raise HTTPException(404, "模型配置不存在")
        base_url = config.base_url
        api_key = decrypt_secret(config.api_key_encrypted)
        model = model or config.text_model
    if not base_url or not api_key:
        raise HTTPException(400, "测试连接需要 base_url 和 api_key")
    success, latency, message = await test_model(base_url=base_url, api_key=api_key, model=model)
    return ModelTestResult(success=success, latency_ms=latency, message=message)


def _model_config_read(config: ModelConfig, key: str) -> ModelConfigRead:
    return ModelConfigRead(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=mask_secret(key) if key else "****",
        text_model=config.text_model,
        vision_model=config.vision_model,
        embedding_model=config.embedding_model,
        embedding_base_url=config.embedding_base_url,
        embedding_api_key_masked="****" if config.embedding_api_key_encrypted else "沿用主模型密钥",
        embedding_dimensions=config.embedding_dimensions,
        is_active=config.is_active,
        config_json=config.config_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/documents/{document_id}/fill-scan", response_model=list[FillSlotRead])
async def scan_fill(document_id: str, session: AsyncSession = Depends(get_session)):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文档不存在")
    slots = await detect_fill_slots(session, document)
    await session.commit()
    return slots


@router.post("/analysis-runs/{run_id}/fill-plan", response_model=FillPlanRead, status_code=201)
async def build_fill_plan(
    run_id: str,
    payload: FillPlanRebuild | None = None,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析任务不存在")
    template = await _select_template(
        session, run.project_id, payload.template_document_id if payload else None
    )
    if template is None:
        raise HTTPException(400, "请先上传投标模板")
    if template.current_revision_id is None:
        raise HTTPException(400, "投标模板尚未解析完成")
    existing = (
        await session.execute(
            select(FillPlan)
            .where(FillPlan.run_id == run_id, FillPlan.document_id == template.id)
            .order_by(FillPlan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        plan = await rebuild_fill_plan(session, existing, project_id=run.project_id)
    else:
        await detect_fill_slots(session, template)
        plan = await create_fill_plan(
            session, run_id=run_id, project_id=run.project_id, template_document=template
        )
    await render_annotations(session, plan)
    await build_checklist(session, run_id)
    await mark_run_complete_if_ready(session, run_id)
    await session.commit()
    return await _load_fill_plan(session, plan.id)


@router.get("/analysis-runs/{run_id}/fill-plan", response_model=FillPlanRead)
async def read_run_fill_plan(
    run_id: str,
    template_document_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(FillPlan).where(FillPlan.run_id == run_id)
    if template_document_id:
        query = query.where(FillPlan.document_id == template_document_id)
    plan = (
        await session.execute(query.order_by(FillPlan.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, "尚未生成填写计划")
    return await _load_fill_plan(session, plan.id)


async def _select_template(
    session: AsyncSession, project_id: str, document_id: str | None = None
) -> Document | None:
    query = select(Document).where(Document.project_id == project_id)
    if document_id:
        query = query.where(Document.id == document_id)
    else:
        query = query.where(Document.role == DocumentRole.TEMPLATE)
    return (
        await session.execute(query.order_by(Document.created_at.desc()).limit(1))
    ).scalar_one_or_none()


@router.get("/fill-plans/{plan_id}", response_model=FillPlanRead)
async def get_fill_plan(plan_id: str, session: AsyncSession = Depends(get_session)):
    return await _load_fill_plan(session, plan_id)


async def _load_fill_plan(session: AsyncSession, plan_id: str) -> FillPlanRead:
    plan = await session.get(FillPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "填写计划不存在")
    targets = (
        (
            await session.execute(
                select(FillTarget)
                .options(selectinload(FillTarget.suggestions))
                .where(FillTarget.plan_id == plan_id)
                .order_by(FillTarget.created_at)
            )
        )
        .scalars()
        .all()
    )
    assets = (
        (
            await session.execute(
                select(AnnotationAsset)
                .where(AnnotationAsset.plan_id == plan_id)
                .order_by(AnnotationAsset.created_at)
            )
        )
        .scalars()
        .all()
    )
    return FillPlanRead(
        **plan.__dict__,
        targets=[FillTargetRead.model_validate(target) for target in targets],
        assets=[AnnotationAssetRead.model_validate(asset) for asset in assets],
    )


@router.patch("/fill-suggestions/{suggestion_id}", response_model=FillSuggestionRead)
async def update_fill_suggestion(
    suggestion_id: str,
    payload: FillSuggestionUpdate,
    session: AsyncSession = Depends(get_session),
):
    suggestion = await session.get(FillSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(404, "填写建议不存在")
    data = payload.model_dump(exclude_unset=True)
    if "value" in data and data["value"] != suggestion.value:
        data.setdefault("status", SuggestionStatus.EDITED.value)
    if data.get("status") is not None:
        data["status"] = SuggestionStatus(data["status"])
    for key, value in data.items():
        setattr(suggestion, key, value)
    suggestion.reviewed_at = datetime.now(UTC)
    await session.commit()
    target = await session.get(FillTarget, suggestion.target_id)
    if target is not None and target.plan_id:
        plan = await session.get(FillPlan, target.plan_id)
        if plan is not None:
            await render_annotations(session, plan)
            await build_checklist(session, plan.run_id)
            await mark_run_complete_if_ready(session, plan.run_id)
            await session.commit()
    return suggestion


@router.get("/annotation-assets/{asset_id}/image")
async def get_annotation_image(asset_id: str, session: AsyncSession = Depends(get_session)):
    asset = await session.get(AnnotationAsset, asset_id)
    if asset is None or not Path(asset.path).exists():
        raise HTTPException(404, "标注图片不存在")
    return FileResponse(asset.path, media_type="image/png")


@router.get("/analysis-runs/{run_id}/checklist", response_model=list[ChecklistRead])
async def list_checklist(run_id: str, session: AsyncSession = Depends(get_session)):
    return (
        (
            await session.execute(
                select(ChecklistItem)
                .where(ChecklistItem.run_id == run_id)
                .order_by(ChecklistItem.created_at)
            )
        )
        .scalars()
        .all()
    )


@router.patch("/checklist/{item_id}", response_model=ChecklistRead)
async def update_checklist(
    item_id: str, payload: ChecklistUpdate, session: AsyncSession = Depends(get_session)
):
    item = await session.get(ChecklistItem, item_id)
    if item is None:
        raise HTTPException(404, "待办不存在")
    item.completed = payload.completed
    await session.commit()
    await mark_run_complete_if_ready(session, item.run_id)
    await session.commit()
    return item


@router.get("/analysis-runs/{run_id}/report", response_model=ReportRead)
async def get_report(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, "分析任务不存在")
    decisions = (
        (
            await session.execute(
                select(Decision)
                .options(selectinload(Decision.requirement).selectinload(Requirement.source_span))
                .options(selectinload(Decision.reviews))
                .where(Decision.run_id == run_id)
                .order_by(Decision.created_at)
            )
        )
        .scalars()
        .all()
    )
    summary = {status.value: 0 for status in DecisionStatus}
    project = await session.get(Project, run.project_id)
    decision_labels = {
        "met": "符合",
        "not_met": "不符合",
        "needs_review": "待人工复核",
        "not_applicable": "不适用",
    }
    mode_label = (
        "人工核对（未执行模型提取）"
        if run.model_snapshot.get("execution_mode") == "manual"
        else "模型分析与人工复核"
    )
    status_labels = {
        "completed": "已完成",
        "needs_review": "待人工复核",
        "stale": "资料已更新，旧结论待重新核对",
        "failed": "分析未完成",
    }
    lines = [
        "# 投标准备检查报告",
        "",
        f"项目：{project.name if project else '未命名项目'}",
        f"招标编号：{project.tender_no or '未填写' if project else '未填写'}",
        f"工作方式：{mode_label}",
        f"分析状态：{status_labels.get(run.status.value, '处理中')}",
        f"生成时间：{datetime.now(UTC).isoformat()}",
        "",
        "## 要求核对结果",
        "",
    ]
    for decision in decisions:
        summary[decision.status.value] += 1
        req = decision.requirement
        span = req.source_span
        source_document = await session.get(Document, span.document_id) if span else None
        source_page = await session.get(Page, span.page_id) if span else None
        lines.extend(
            [
                f"### {req.title}",
                "",
                f"- 结论：{decision_labels[decision.status.value]}",
                f"- 说明：{decision.summary}",
                f"- 来源：{source_document.filename if source_document else '缺失'}"
                f" · 第 {source_page.page_index + 1 if source_page else '?'} 页",
                f"- 结论有效性：{'待重新核对' if decision.stale else '当前记录'}",
                f"- 原文：{req.source_span.quote if req.source_span else '缺失'}",
                "",
            ]
        )
        for review in sorted(decision.reviews, key=lambda item: item.created_at):
            lines.append(
                f"- 人工复核（{review.created_at.isoformat()}）："
                f"{decision_labels.get(review.new_status, review.new_status)}；{review.reason}"
            )
        evidence = (
            (
                await session.execute(
                    select(EvidenceItem).where(EvidenceItem.id.in_(decision.evidence_ids))
                )
            )
            .scalars()
            .all()
        )
        for item in evidence:
            lines.append(f"- 支持证据：{item.title}（{item.holder or '主体未填写'}）")
        lines.append("")
    if run.coverage_notes:
        lines.extend(
            [
                "## 提取范围与人工核验",
                "",
                *[f"- {note}" for note in run.coverage_notes],
                "",
            ]
        )
    checklist = (
        (await session.execute(select(ChecklistItem).where(ChecklistItem.run_id == run_id)))
        .scalars()
        .all()
    )
    lines.extend(["## 交付检查清单", ""])
    for item in checklist:
        lines.append(f"- [{'x' if item.completed else ' '}] {item.title}")
        if item.detail:
            lines.append(f"  - {item.detail}")
    if not checklist:
        lines.append("暂无检查事项。")
    fill_rows = (
        await session.execute(
            select(FillTarget, FillSuggestion, Document, Page)
            .join(FillPlan, FillPlan.id == FillTarget.plan_id)
            .join(Document, Document.id == FillPlan.document_id)
            .join(Page, Page.id == FillTarget.page_id)
            .outerjoin(FillSuggestion, FillSuggestion.target_id == FillTarget.id)
            .where(FillPlan.run_id == run_id)
            .order_by(FillTarget.created_at)
        )
    ).all()
    lines.extend(["", "## 模板填写建议", ""])
    suggestion_labels = {
        "accepted": "已确认",
        "edited": "已修改",
        "proposed": "待确认",
        "missing_evidence": "待补充",
        "rejected": "未采用",
    }
    for target, suggestion, document, page in fill_rows:
        value = suggestion.value if suggestion and suggestion.value else "尚未填写"
        status = suggestion_labels.get(suggestion.status, "待补充") if suggestion else "待补充"
        lines.extend(
            [
                f"### {target.label}",
                "",
                f"- 位置：{document.filename} · 第 {page.page_index + 1} 页",
                f"- 状态：{status}",
                f"- 内容：{value}",
                "",
            ]
        )
    if not fill_rows:
        lines.append("尚未生成填写建议。")
    return ReportRead(
        run_id=run.id,
        generated_at=datetime.now(UTC),
        markdown="\n".join(lines),
        summary=summary,
    )


@router.get("/analysis-runs/{run_id}/checklist/auto", response_model=list[ChecklistRead])
async def auto_checklist(run_id: str, session: AsyncSession = Depends(get_session)):
    items = await build_checklist(session, run_id)
    await session.commit()
    return items
