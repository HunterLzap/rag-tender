"""Customer workflow orchestration; model calls remain behind the runtime switch."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    Bid,
    Document,
    EvidenceItem,
    Job,
    JobStatus,
    ModelConfig,
    Organization,
    Project,
    ProjectStatus,
    ResponseValue,
)
from app.services.jobs import enqueue
from app.services.library import document_scope
from app.services.model_gateway import ModelGatewayError, embedding_signature
from app.storage import sha256_text


async def pipeline_config(session: AsyncSession, config_id: str | None = None) -> ModelConfig:
    query = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    if config_id:
        query = query.where(ModelConfig.id == config_id)
    config = (
        await session.execute(query.order_by(ModelConfig.updated_at.desc()).limit(1))
    ).scalar_one_or_none()
    if config is None:
        raise ModelGatewayError("请配置并启用主模型和 Embedding 模型")
    if not config.embedding_model:
        raise ModelGatewayError("请在模型设置中补充 Embedding 模型")
    return config


async def queue_document_processing(
    session: AsyncSession,
    document: Document,
    *,
    config_id: str | None = None,
) -> None:
    metadata = dict(document.metadata_json or {})
    if not get_settings().live_model_calls:
        document.metadata_json = {**metadata, "ai_status": "waiting_api", "ai_error": None}
        return
    try:
        config = await pipeline_config(session, config_id)
    except ModelGatewayError as exc:
        document.metadata_json = {
            **metadata,
            "ai_status": "waiting_config",
            "ai_error": str(exc),
        }
        return
    document.metadata_json = {**metadata, "ai_status": "queued", "ai_error": None}
    await enqueue(
        session,
        "process_document",
        {
            "document_id": document.id,
            "model_config_id": config.id,
            "_dedupe_key": f"process:{document.id}",
        },
    )


async def project_inputs(
    session: AsyncSession,
    project: Project,
    config: ModelConfig,
) -> tuple[list[Document], list[dict], str]:
    documents = (
        (
            await session.execute(
                select(Document).where(document_scope(project)).order_by(Document.id)
            )
        )
        .scalars()
        .all()
    )
    snapshot = [
        {
            "document_id": document.id,
            "revision_id": document.current_revision_id,
            "text_version": (document.metadata_json or {}).get("text_version", 0),
            "scope": "enterprise" if document.organization_id else "project",
        }
        for document in documents
    ]
    values = (
        await session.execute(
            select(ResponseValue.id, ResponseValue.version)
            .where(ResponseValue.project_id == project.id)
            .order_by(ResponseValue.id)
        )
    ).all()
    evidence = (
        await session.execute(
            select(EvidenceItem.id, EvidenceItem.updated_at)
            .where(
                (EvidenceItem.project_id == project.id)
                | (EvidenceItem.organization_id == project.organization_id)
                if project.organization_id
                else EvidenceItem.project_id == project.id
            )
            .order_by(EvidenceItem.id)
        )
    ).all()
    organization = (
        await session.get(Organization, project.organization_id)
        if project.organization_id
        else None
    )
    signature = sha256_text(
        json.dumps(
            {
                "documents": snapshot,
                "values": [list(row) for row in values],
                "evidence": [[row[0], str(row[1])] for row in evidence],
                "deadline": str(project.bid_deadline),
                "organization": [organization.id, str(organization.updated_at)]
                if organization
                else None,
                "model": [
                    config.base_url,
                    config.text_model,
                    config.vision_model,
                    embedding_signature(config),
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return documents, snapshot, signature


async def schedule_analysis(
    session: AsyncSession,
    project: Project,
    *,
    automatic: bool = False,
    config_id: str | None = None,
    prompt_version: str = "v2.1",
    ruleset_version: str = "v2.1",
) -> tuple[AnalysisRun, Job] | None:
    if not get_settings().live_model_calls:
        if automatic:
            return None
        raise ModelGatewayError("开发阶段未启用真实模型，分析任务尚未执行")
    if automatic and not project.organization_id:
        return None
    try:
        config = await pipeline_config(session, config_id)
    except ModelGatewayError:
        if automatic:
            return None
        raise
    documents, snapshot, signature = await project_inputs(session, project, config)
    tenders = [document for document in documents if document.role in {"tender", "addendum", "qa"}]
    if not tenders or any(
        not document.current_revision_id
        or (document.metadata_json or {}).get("parse_status") in {"queued", "running", "failed"}
        or (document.metadata_json or {}).get("ai_status") not in {"ready", "needs_review"}
        for document in documents
    ):
        if automatic:
            return None
        raise ModelGatewayError("请等待招标文件和企业材料完成 AI 入库")
    active = (
        await session.execute(
            select(Job)
            .where(
                Job.payload["project_id"].as_string() == project.id,
                Job.kind == "analyze_project",
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if active:
        return await session.get(AnalysisRun, active.payload["run_id"]), active
    if automatic:
        latest = (
            await session.execute(
                select(AnalysisRun)
                .where(AnalysisRun.project_id == project.id)
                .order_by(AnalysisRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest and latest.model_snapshot.get("input_signature") == signature:
            return None
    bid = (
        await session.execute(
            select(Bid).where(Bid.project_id == project.id).order_by(Bid.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    run = AnalysisRun(
        project_id=project.id,
        bid_id=bid.id if bid else None,
        status=AnalysisStatus.DRAFT,
        input_snapshot=snapshot,
        prompt_version=prompt_version,
        ruleset_version=ruleset_version,
        model_snapshot={
            "model_config_id": config.id,
            "provider": config.provider,
            "text_model": config.text_model,
            "vision_model": config.vision_model or config.text_model,
            "embedding_model": config.embedding_model,
            "input_signature": signature,
            "automatic": automatic,
        },
    )
    session.add(run)
    await session.flush()
    job = await enqueue(
        session,
        "analyze_project",
        {
            "run_id": run.id,
            "model_config_id": config.id,
            "_dedupe_key": f"analyze:{run.id}",
        },
    )
    return run, job


async def schedule_related_projects(
    session: AsyncSession,
    document: Document | EvidenceItem,
) -> None:
    query = select(Project).where(
        Project.auto_analyze.is_(True),
        Project.status == ProjectStatus.ACTIVE,
    )
    if document.project_id:
        query = query.where(Project.id == document.project_id)
    else:
        query = query.where(Project.organization_id == document.organization_id)
    for project in (await session.execute(query)).scalars().all():
        await schedule_analysis(session, project, automatic=True)


async def resume_pending_documents(session: AsyncSession) -> int:
    """Resume uploads that waited for model configuration or the runtime switch."""
    if not get_settings().live_model_calls:
        return 0
    try:
        config = await pipeline_config(session)
    except ModelGatewayError:
        return 0
    documents = (
        (
            await session.execute(
                select(Document).where(
                    Document.current_revision_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    count = 0
    for document in documents:
        metadata = document.metadata_json or {}
        pending = metadata.get("ai_status", "pending") in {
            "pending",
            "waiting_api",
            "waiting_config",
        }
        needs_index = (
            document.role == "evidence"
            and metadata.get("ai_status") in {"ready", "needs_review"}
            and metadata.get("embedding_signature") != embedding_signature(config)
        )
        if (pending or needs_index) and metadata.get("parse_status") not in {
            "queued",
            "running",
            "failed",
        }:
            await queue_document_processing(session, document)
            count += 1
    await session.commit()
    return count
