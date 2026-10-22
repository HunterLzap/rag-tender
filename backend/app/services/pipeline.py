"""Customer workflow orchestration; model calls remain behind the runtime switch."""

import json
from datetime import UTC, datetime

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


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    # SQLite reloads UTC timestamps without tzinfo; both representations are one input.
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else (
        value.astimezone(UTC).isoformat()
    )


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
        document.metadata_json = {
            **metadata,
            "ai_status": "waiting_api",
            "ai_error": None,
            "auto_process": False,
        }
        return
    # Only live uploads and explicitly selected reprocessing join automatic recovery.
    metadata["auto_process"] = True
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
    # A worker session lives across model requests; other sessions can edit its inputs.
    await session.flush()
    await session.refresh(project)
    await session.refresh(config)
    documents = (
        (
            await session.execute(
                select(Document).where(document_scope(project)).order_by(Document.id)
                .execution_options(populate_existing=True)
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
            "role": document.role,
            "ai_status": (document.metadata_json or {}).get("ai_status"),
            "parse_status": (document.metadata_json or {}).get("parse_status"),
            "supersedes_id": document.supersedes_id,
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
        await session.get(Organization, project.organization_id, populate_existing=True)
        if project.organization_id
        else None
    )
    bid = (
        await session.execute(
            select(Bid)
            .where(Bid.project_id == project.id)
            .execution_options(populate_existing=True)
            .order_by(Bid.created_at.desc(), Bid.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    signature = sha256_text(
        json.dumps(
            {
                "documents": snapshot,
                "values": [list(row) for row in values],
                "evidence": [[row[0], _timestamp(row[1])] for row in evidence],
                "deadline": _timestamp(project.bid_deadline),
                "project": [project.name, project.tender_no, project.bidder_name, project.timezone],
                "bid": [
                    bid.id,
                    bid.bidder_name,
                    bid.lot_code,
                    _timestamp(bid.bid_deadline),
                    str(bid.as_of_date),
                    bid.status,
                ]
                if bid
                else None,
                "organization": [organization.id, _timestamp(organization.updated_at)]
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
        raise ModelGatewayError("模型服务暂不可用，请稍后开始分析")
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
    if automatic and not any(
        (document.metadata_json or {}).get("auto_process") for document in tenders
    ):
        return None
    if not tenders or any(
        not document.current_revision_id
        or (document.metadata_json or {}).get("parse_status") in {"queued", "running", "failed"}
        or (document.metadata_json or {}).get("ai_status") not in {"ready", "needs_review"}
        for document in documents
        if document.project_id == project.id
    ):
        if automatic:
            return None
        raise ModelGatewayError("请等待项目招标文件和模板完成 AI 入库")
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
            select(Bid)
            .where(Bid.project_id == project.id)
            .order_by(Bid.created_at.desc(), Bid.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    run = AnalysisRun(
        project_id=project.id,
        bid_id=bid.id if bid else None,
        status=AnalysisStatus.DRAFT,
        input_snapshot=snapshot,
        coverage_notes=[
            f"企业材料未完成入库：{document.filename}"
            for document in documents
            if document.organization_id
            and (document.metadata_json or {}).get("ai_status") not in {"ready", "needs_review"}
        ],
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


async def resume_analysis(session: AsyncSession, run: AnalysisRun) -> Job:
    if not get_settings().live_model_calls:
        raise ModelGatewayError("模型服务暂不可用，请稍后继续分析")
    if run.status != AnalysisStatus.FAILED:
        raise ModelGatewayError("仅失败或取消的分析可以继续")
    config = await pipeline_config(session)
    project = await session.get(Project, run.project_id)
    _, _, signature = await project_inputs(session, project, config)
    if signature != run.model_snapshot.get("input_signature"):
        raise ModelGatewayError("资料或模型配置已变化，请返回项目重新自动对标")
    previous = (await session.execute(
        select(Job).where(Job.kind == "analyze_project",
                          Job.payload["run_id"].as_string() == run.id)
        .order_by(Job.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if previous is None or previous.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
        raise ModelGatewayError("本次分析没有可以继续的中断任务")
    job = await enqueue(session, "analyze_project", {
        "run_id": run.id, "model_config_id": config.id, "resume": True,
        "input_signature": signature, "_dedupe_key": f"analyze:{run.id}",
    })
    job.result = dict(previous.result or {})
    run.model_snapshot = {**run.model_snapshot, "model_config_id": config.id}
    run.status = AnalysisStatus.DRAFT
    run.progress = 0
    run.stage = "queued"
    run.error = None
    run.finished_at = None
    return job


async def resume_pending_documents(session: AsyncSession) -> int:
    """Resume enrolled live uploads; never enroll historical/development files implicitly."""
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
        if not metadata.get("auto_process"):
            continue
        pending = metadata.get("ai_status") in {
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
            "canceled",
        }:
            await queue_document_processing(session, document)
            count += 1
    # Recover a crash between committing ready documents and scheduling their analysis.
    projects = (await session.execute(select(Project).where(
        Project.auto_analyze.is_(True), Project.status == ProjectStatus.ACTIVE,
    ))).scalars().all()
    for project in projects:
        await schedule_analysis(session, project, automatic=True)
    await session.commit()
    return count
