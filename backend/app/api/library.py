from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes import _document_read, _read_documents
from app.config import get_settings
from app.db import get_session, utcnow
from app.models import (
    Document,
    DocumentRole,
    EvidenceFact,
    EvidenceItem,
    EvidenceStatus,
    FillPlan,
    Job,
    Organization,
    Project,
    SourceSpan,
)
from app.schemas import (
    DocumentRead,
    EvidenceFactRead,
    EvidenceFactUpdate,
    EvidenceRead,
    JobRead,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.services.jobs import enqueue
from app.services.library import mark_organization_stale
from app.services.pipeline import (
    pipeline_config,
    queue_document_processing,
    schedule_analysis,
    schedule_related_projects,
)
from app.storage import store_upload

router = APIRouter()


async def _organization(session: AsyncSession, organization_id: str) -> Organization:
    item = await session.get(Organization, organization_id)
    if item is None:
        raise HTTPException(404, "企业不存在")
    return item


@router.get("/organizations", response_model=list[OrganizationRead])
async def list_organizations(session: AsyncSession = Depends(get_session)):
    organizations = (
        (await session.execute(select(Organization).order_by(Organization.created_at)))
        .scalars()
        .all()
    )
    result = []
    for item in organizations:
        documents = (
            await session.execute(
                select(func.count(Document.id)).where(
                    Document.organization_id == item.id,
                )
            )
        ).scalar_one()
        evidence = (
            await session.execute(
                select(func.count(EvidenceItem.id)).where(
                    EvidenceItem.organization_id == item.id,
                )
            )
        ).scalar_one()
        result.append(
            OrganizationRead(
                **item.__dict__,
                document_count=documents,
                evidence_count=evidence,
            )
        )
    return result


@router.post("/organizations", response_model=OrganizationRead, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    session: AsyncSession = Depends(get_session),
):
    duplicate = (
        await session.execute(
            select(Organization.id).where(Organization.name == payload.name.strip())
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(409, "企业名称已存在")
    item = Organization(**payload.model_dump())
    item.name = item.name.strip()
    session.add(item)
    await session.commit()
    return item


@router.patch("/organizations/{organization_id}", response_model=OrganizationRead)
async def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    session: AsyncSession = Depends(get_session),
):
    item = await _organization(session, organization_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        duplicate = (
            await session.execute(
                select(Organization.id).where(
                    Organization.name == data["name"],
                    Organization.id != organization_id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(409, "企业名称已存在")
    for key, value in data.items():
        setattr(item, key, value)
    await mark_organization_stale(session, organization_id)
    for project in (
        await session.execute(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.auto_analyze.is_(True),
                Project.status == "active",
            )
        )
    ).scalars():
        await schedule_analysis(session, project, automatic=True)
    await session.commit()
    return item


@router.delete("/organizations/{organization_id}", status_code=204)
async def delete_organization(
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    item = await _organization(session, organization_id)
    for model in (Document, Project):
        if (
            await session.execute(
                select(model.id).where(model.organization_id == organization_id).limit(1)
            )
        ).scalar_one_or_none():
            raise HTTPException(409, "请先移除企业材料并解除项目关联")
    await session.delete(item)
    await session.commit()


@router.get("/organizations/{organization_id}/documents", response_model=list[DocumentRead])
async def list_library_documents(
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    await _organization(session, organization_id)
    documents = (
        (
            await session.execute(
                select(Document)
                .where(
                    Document.organization_id == organization_id,
                )
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return await _read_documents(session, documents)


@router.get("/projects/{project_id}/library-documents", response_model=list[DocumentRead])
async def project_library_documents(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    if not project.organization_id:
        return []
    documents = (
        (
            await session.execute(
                select(Document)
                .where(
                    Document.organization_id == project.organization_id,
                )
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return await _read_documents(session, documents)


@router.post(
    "/organizations/{organization_id}/documents",
    response_model=DocumentRead,
    status_code=201,
)
async def upload_library_document(
    organization_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    await _organization(session, organization_id)
    if Path(file.filename or "").suffix.lower() not in {
        ".pdf",
        ".doc",
        ".docx",
        ".xlsx",
        ".csv",
        ".png",
        ".jpg",
        ".jpeg",
    }:
        raise HTTPException(400, "请选择 PDF、Word、Excel、CSV 或图片")
    content = await file.read()
    if not content or len(content) > get_settings().max_upload_bytes:
        raise HTTPException(400, "文件为空或超过上传大小限制")
    stored = store_upload(file.filename, content)
    duplicate = (
        await session.execute(
            select(Document).where(
                Document.organization_id == organization_id,
                Document.sha256 == stored.sha256,
                Document.role == DocumentRole.EVIDENCE,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        return _document_read(duplicate)
    document = Document(
        organization_id=organization_id,
        role=DocumentRole.EVIDENCE,
        filename=file.filename,
        content_type=file.content_type,
        storage_path=str(stored.path),
        sha256=stored.sha256,
        file_size=stored.size,
        metadata_json={"parse_status": "queued", "ai_status": "pending"},
    )
    session.add(document)
    await session.flush()
    await enqueue(
        session,
        "parse_document",
        {
            "document_id": document.id,
            "_dedupe_key": f"parse:{document.id}",
        },
    )
    await mark_organization_stale(session, organization_id)
    await session.commit()
    return _document_read(document)


@router.get("/organizations/{organization_id}/evidence", response_model=list[EvidenceRead])
async def list_library_evidence(
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    await _organization(session, organization_id)
    return (
        (
            await session.execute(
                select(EvidenceItem)
                .join(SourceSpan, SourceSpan.id == EvidenceItem.source_span_id)
                .join(Document, Document.id == SourceSpan.document_id)
                .where(
                    EvidenceItem.organization_id == organization_id,
                    EvidenceItem.status != EvidenceStatus.ARCHIVED,
                    SourceSpan.revision_id == Document.current_revision_id,
                )
                .options(
                    selectinload(EvidenceItem.facts).selectinload(EvidenceFact.source_span),
                    selectinload(EvidenceItem.source_span),
                )
                .order_by(EvidenceItem.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.patch("/evidence-facts/{fact_id}", response_model=EvidenceFactRead)
async def edit_evidence_fact(
    fact_id: str,
    payload: EvidenceFactUpdate,
    session: AsyncSession = Depends(get_session),
):
    fact = await session.get(EvidenceFact, fact_id)
    if fact is None:
        raise HTTPException(404, "字段不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(fact, key, value)
    fact.extraction_method = "manual"
    evidence = await session.get(EvidenceItem, fact.evidence_id)
    evidence.updated_at = utcnow()
    value = fact.value_text
    if fact.value_number is not None:
        value = str(fact.value_number)
    if fact.value_date is not None:
        value = fact.value_date.isoformat()
    evidence.payload = {**evidence.payload, fact.fact_key: value}
    if fact.fact_key in {"valid_until", "expiry_date"}:
        evidence.valid_until = fact.value_date
    if evidence.organization_id:
        await mark_organization_stale(session, evidence.organization_id)
    else:
        from app.services.freshness import mark_project_stale

        await mark_project_stale(session, evidence.project_id)
    await schedule_related_projects(session, evidence)
    await session.commit()
    return (
        await session.execute(
            select(EvidenceFact)
            .where(EvidenceFact.id == fact.id)
            .options(selectinload(EvidenceFact.source_span))
        )
    ).scalar_one()


@router.get("/organizations/{organization_id}/jobs", response_model=list[JobRead])
async def list_library_jobs(
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    return (
        (
            await session.execute(
                select(Job)
                .where(
                    Job.payload["organization_id"].as_string() == organization_id,
                )
                .order_by(Job.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )


@router.post("/documents/{document_id}/process", response_model=DocumentRead)
async def process_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
):
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "文件不存在")
    if not get_settings().live_model_calls:
        raise HTTPException(409, "开发阶段模型接口未启用，未执行 AI 入库")
    if not document.current_revision_id:
        raise HTTPException(409, "请先完成文档解析")
    await queue_document_processing(session, document)
    await session.commit()
    return _document_read(document)


@router.post("/fill-plans/{plan_id}/draft", response_model=JobRead, status_code=202)
async def draft_fill_plan(plan_id: str, session: AsyncSession = Depends(get_session)):
    if not get_settings().live_model_calls:
        raise HTTPException(409, "开发阶段模型接口未启用，未执行 AI 起草")
    plan = await session.get(FillPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "填写计划不存在")
    from app.services.model_gateway import ModelGatewayError

    try:
        config = await pipeline_config(session)
    except ModelGatewayError as exc:
        raise HTTPException(409, str(exc)) from exc
    plan.status = "queued"
    job = await enqueue(
        session,
        "draft_fill_plan",
        {
            "plan_id": plan.id,
            "model_config_id": config.id,
            "_dedupe_key": f"draft:{plan.id}",
        },
    )
    await session.commit()
    return job


@router.post("/documents/{document_id}/share", response_model=DocumentRead)
async def share_project_document(
    document_id: str,
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    await _organization(session, organization_id)
    document = await session.get(Document, document_id)
    if document is None or document.role != DocumentRole.EVIDENCE or not document.project_id:
        raise HTTPException(400, "请选择项目内的证明材料")
    duplicate = (
        await session.execute(
            select(Document.id).where(
                Document.organization_id == organization_id,
                Document.sha256 == document.sha256,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(409, "企业库已有同一文件，请直接引用")
    project = await session.get(Project, document.project_id)
    project.organization_id = organization_id
    evidence = (
        (
            await session.execute(
                select(EvidenceItem)
                .join(SourceSpan, SourceSpan.id == EvidenceItem.source_span_id)
                .where(SourceSpan.document_id == document.id)
            )
        )
        .scalars()
        .all()
    )
    for item in evidence:
        item.organization_id = organization_id
        item.project_id = None
    document.project_id = None
    document.organization_id = organization_id
    await mark_organization_stale(session, organization_id)
    await session.commit()
    await schedule_related_projects(session, document)
    await session.commit()
    return _document_read(document)
