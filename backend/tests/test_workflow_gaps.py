"""Focused regressions for the handoff gaps; all model/network work is stubbed."""

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.models import Bid, Document, Job, ModelConfig, Organization, Project
from app.services import pipeline


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    async def blocked(*args, **kwargs):
        raise AssertionError("Network calls are forbidden in these regressions")

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)


def live_pipeline(monkeypatch):
    monkeypatch.setattr(pipeline, "get_settings", lambda: SimpleNamespace(live_model_calls=True))


async def document(session, project=None, organization=None, role="evidence", metadata=None):
    item = Document(
        project_id=project.id if project else None,
        organization_id=organization.id if organization else None,
        role=role,
        filename="test.csv",
        storage_path="unused",
        sha256="test",
        file_size=1,
        current_revision_id="revision",
        metadata_json=metadata or {},
    )
    session.add(item)
    await session.flush()
    return item


async def project_config(session):
    organization = Organization(name="Acme")
    config = ModelConfig(
        name="stub",
        provider="openai",
        base_url="https://unused.invalid",
        text_model="stub",
        embedding_model="stub",
        is_active=True,
        api_key_encrypted="stub",
    )
    session.add_all([organization, config])
    await session.flush()
    project = Project(name="Tender", organization_id=organization.id)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project, config, organization


async def test_resume_only_enrolled_live_uploads(session, monkeypatch):
    project, config, organization = await project_config(session)
    legacy = await document(session, organization=organization)
    development = await document(session, project=project, role="tender")
    await pipeline.queue_document_processing(session, development)
    assert development.metadata_json["ai_status"] == "waiting_api"
    live_pipeline(monkeypatch)
    assert await pipeline.resume_pending_documents(session) == 0
    assert legacy.metadata_json == {}
    config.is_active = False
    await session.flush()
    fresh = await document(session, project=project, role="template")
    await pipeline.queue_document_processing(session, fresh)
    assert fresh.metadata_json["ai_status"] == "waiting_config"
    config.is_active = True
    await session.flush()
    assert await pipeline.resume_pending_documents(session) == 1
    assert await pipeline.resume_pending_documents(session) == 0
    jobs = (await session.execute(select(Job))).scalars().all()
    assert [job.payload["document_id"] for job in jobs] == [fresh.id]


async def test_signature_and_unrelated_failed_material(session, monkeypatch):
    project, config, organization = await project_config(session)
    await document(
        session,
        project=project,
        role="tender",
        metadata={"ai_status": "ready", "auto_process": True},
    )
    await document(session, organization=organization, metadata={"ai_status": "failed"})
    original = (await pipeline.project_inputs(session, project, config))[2]
    for field, value in [
        ("name", "Changed"),
        ("tender_no", "T-02"),
        ("bidder_name", "New bidder"),
        ("timezone", "UTC"),
    ]:
        setattr(project, field, value)
        changed = (await pipeline.project_inputs(session, project, config))[2]
        assert changed != original
        original = changed
    bid = Bid(project_id=project.id, bidder_name="Acme", lot_code="A")
    session.add(bid)
    await session.flush()
    changed = (await pipeline.project_inputs(session, project, config))[2]
    assert changed != original
    bid.lot_code = "B"
    assert (await pipeline.project_inputs(session, project, config))[2] != changed
    live_pipeline(monkeypatch)
    run, job = await pipeline.schedule_analysis(session, project, automatic=True)
    assert run.coverage_notes and job.payload["project_id"] == project.id
    assert (await pipeline.schedule_analysis(session, project, automatic=True))[0].id == run.id


async def source(session, doc, quote="Original text"):
    from app.models import DocumentRevision, Page, SourceSpan

    revision = DocumentRevision(document_id=doc.id, revision_no=1)
    session.add(revision)
    await session.flush()
    doc.current_revision_id = revision.id
    page = Page(
        document_id=doc.id, revision_id=revision.id, page_index=0, width=600, height=800, text=quote
    )
    session.add(page)
    await session.flush()
    span = SourceSpan(
        document_id=doc.id,
        revision_id=revision.id,
        page_id=page.id,
        quote=quote,
        quote_hash="test",
        bbox_json=[0, 0, 600, 800],
    )
    session.add(span)
    await session.flush()
    return span, page


async def requirement(session, run, span, statement, condition=None):
    from app.models import Requirement

    item = Requirement(
        run_id=run.id,
        category="qualification",
        title=statement,
        statement=statement,
        source_span_id=span.id,
        fingerprint=statement,
        condition_json=condition or {"type": "semantic"},
    )
    session.add(item)
    await session.flush()
    return item


@pytest.mark.parametrize("valid", [True, False])
async def test_amendment_replacement_or_conflict_and_manual_resolution(session, monkeypatch, valid):
    from datetime import date

    from app.api.routes import update_requirement
    from app.models import AnalysisRun, AnalysisStatus
    from app.schemas import RequirementUpdate
    from app.services import requirement_versions as versions
    from app.services.comparison import compare_requirement

    project, _, _ = await project_config(session)
    run = AnalysisRun(project_id=project.id, status=AnalysisStatus.NEEDS_REVIEW)
    session.add(run)
    await session.flush()
    base_doc = await document(session, project=project, role="tender")
    new_doc = await document(session, project=project, role="addendum")
    base_span, _ = await source(session, base_doc, "合同金额不少于500万元")
    new_span, _ = await source(session, new_doc, "原合同金额500万元更正为300万元")
    old = await requirement(session, run, base_span, base_span.quote)
    new = await requirement(session, run, new_span, new_span.quote)

    async def relations(*args, **kwargs):
        return versions.Relations(
            relations=[
                versions.Relation(
                    prior_id=old.id,
                    relation="replaces",
                    prior_quote=base_span.quote,
                    amendment_quote=new_span.quote if valid else "fabricated",
                    reason="更正金额",
                )
            ]
        )

    monkeypatch.setattr(versions, "get_settings", lambda: SimpleNamespace(live_model_calls=True))
    monkeypatch.setattr(versions, "structured_text", relations)
    await versions.resolve_requirement_versions(session, run.id)
    replaced, conflicts = versions.version_state([old, new])
    if valid:
        assert replaced[old.id] == new.id and not conflicts
        result = await compare_requirement(
            session, project=project, requirement=old, as_of=date(2026, 1, 1), use_model=False
        )
        assert result["status"] == "not_applicable"
    else:
        assert not replaced and conflicts == {old.id, new.id}
        result = await compare_requirement(
            session, project=project, requirement=new, as_of=date(2026, 1, 1), use_model=False
        )
        assert result["status"] == "needs_review"
        from app.models import Decision, DecisionStatus

        unrelated = await requirement(session, run, base_span, "Unrelated requirement")
        preserved = Decision(run_id=run.id, requirement_id=unrelated.id,
                             status=DecisionStatus.MET, summary="Already reviewed")
        session.add(preserved)
        await session.flush()
        await update_requirement(
            new.id, RequirementUpdate(supersedes_ids=[old.id], version_confirmed=True), session
        )
        replaced, conflicts = versions.version_state([old, new])
        assert replaced[old.id] == new.id and not conflicts
        await session.refresh(preserved)
        assert preserved.status == "met" and preserved.summary == "Already reviewed"
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await update_requirement(old.id, RequirementUpdate(supersedes_ids=[new.id]), session)
        assert exc.value.status_code == 400
    assert (await session.get(type(base_span), old.source_span_id)).quote == base_span.quote


def candidate(identifier, kind="qualification", holder="Acme", entity=None, subject=None):
    return SimpleNamespace(
        evidence=SimpleNamespace(
            id=identifier,
            kind=kind,
            holder=holder,
            identifier=identifier,
            payload={"entity_key": entity, "subject_key": subject},
        )
    )


def fact(key, text=None, number=None, value_date=None, unit=None):
    return SimpleNamespace(
        fact_key=key, value_text=text, value_number=number, value_date=value_date, unit=unit
    )


def certificate(name):
    return {"type": "certificate", "certificate": name}


def test_joint_certificates_keep_validity_and_subject_boundaries():
    from datetime import date

    from app.services.comparison import compare_joint

    condition = {"logic": "all", "conditions": [certificate("ISO9001"), certificate("CCC")]}
    candidates = [candidate("a"), candidate("b")]
    facts = {
        key: [fact("certificate_name", text=name), fact("valid_until", value_date=date(2027, 1, 1))]
        for key, name in [("a", "ISO9001"), ("b", "CCC")]
    }
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1))[0] == "met"
    # Another company's certificate cannot complete this company's proof.
    candidates[1] = candidate("b", holder="Other")
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1))[0] != "met"
    candidates[1] = candidate("b")
    facts["a"][1].value_date = date(2025, 1, 1)
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1))[0] != "met"
    # Even under one employer, different people cannot contribute half the requirement each.
    facts["a"][1].value_date = date(2027, 1, 1)
    candidates = [
        candidate("a", kind="personnel", subject="Alice"),
        candidate("b", kind="personnel", subject="Bob"),
    ]
    assert (
        compare_joint(condition, candidates, facts, None, date(2026, 1, 1), category="personnel")[0]
        != "met"
    )
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1),
                         category="personnel", bidder="Other")[0] != "met"
    candidates[1].evidence.payload["subject_key"] = "Alice"
    assert (
        compare_joint(condition, candidates, facts, None, date(2026, 1, 1), category="personnel")[0]
        == "met"
    )


def test_nested_performance_requires_contract_and_acceptance_for_each_project():
    from datetime import date
    from decimal import Decimal

    from app.services.comparison import compare_joint

    performance = {
        "type": "performance",
        "minimum_count": 1,
        "minimum_amount": 300,
        "unit": "万元",
        "since": "2024-01-01",
        "date_field": "acceptance_date",
        "required_materials": ["contract", "acceptance_certificate"],
    }
    condition = {
        "logic": "all",
        "conditions": [
            certificate("ISO9001"),
            {"logic": "any", "conditions": [performance, certificate("CCC")]},
        ],
    }
    candidates = [
        candidate("cert"),
        candidate("contract", kind="performance", entity="P1"),
        candidate("acceptance", kind="performance", entity="P1"),
    ]
    facts = {
        "cert": [
            fact("certificate_name", text="ISO9001"),
            fact("valid_until", value_date=date(2027, 1, 1)),
        ],
        "contract": [
            fact("contract_amount", number=Decimal(500), unit="万元"),
            fact("material_type", text="contract"),
        ],
        "acceptance": [
            fact("acceptance_date", value_date=date(2025, 1, 1)),
            fact("material_type", text="acceptance_certificate"),
        ],
    }
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1))[0] == "met"
    candidates[2].evidence.payload["entity_key"] = "P2"
    assert compare_joint(condition, candidates, facts, None, date(2026, 1, 1))[0] != "met"


@pytest.mark.parametrize("mode", ["complete", "missing", "duplicate", "uncovered"])
async def test_model_cannot_pass_with_incomplete_condition_coverage(session, monkeypatch, mode):
    from datetime import date

    from app.models import AnalysisRun, EvidenceFact, EvidenceItem
    from app.services import comparison
    from app.services.retrieval import EvidenceCandidate

    project, _, _ = await project_config(session)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    await session.flush()
    doc = await document(session, project=project, role="tender")
    span, _ = await source(session, doc, "须有ISO9001且有效")
    req = await requirement(session, run, span, span.quote, certificate("ISO9001"))
    evidence = EvidenceItem(
        project_id=project.id,
        kind="qualification",
        title="ISO9001",
        holder="Acme",
        source_span_id=span.id,
        fingerprint="cert",
        review_status="verified",
    )
    session.add(evidence)
    await session.flush()
    session.add_all(
        [
            EvidenceFact(
                evidence_id=evidence.id,
                fact_key="certificate_name",
                value_text="ISO9001",
                source_span_id=span.id,
                review_status="verified",
            ),
            EvidenceFact(
                evidence_id=evidence.id,
                fact_key="valid_until",
                value_date=date(2027, 1, 1),
                source_span_id=span.id,
                review_status="verified",
            ),
        ]
    )
    await session.flush()

    async def recall(*args, **kwargs):
        return [EvidenceCandidate(evidence=evidence, score=1, reasons=())]

    async def assess(*args, **kwargs):
        import json

        payload = json.loads(kwargs["user"])
        assert payload["requirement_quote"] == span.quote
        assert {item["condition_id"] for item in payload["condition_catalog"]} == {"c", "scope"}
        ids = ["c", "scope"] if mode != "missing" else ["c"]
        if mode == "duplicate":
            ids.append("c")
        return comparison.Comparison(
            verdict="supports",
            reason="支持",
            coverage_complete=True,
            missing_conditions=["遗漏提交材料"] if mode == "uncovered" else [],
            conditions=[
                comparison.ConditionCheck(
                    condition_id=identifier,
                    label=identifier,
                    status="supports",
                    reason="有原文",
                    evidence_ids=[evidence.id],
                    source_span_ids=[span.id],
                )
                for identifier in ids
            ],
        )

    monkeypatch.setattr(comparison, "recall_evidence", recall)
    monkeypatch.setattr(comparison, "structured_text", assess)
    result = await comparison.compare_requirement(
        session, project=project, requirement=req, as_of=date(2026, 1, 1), use_model=True
    )
    assert result["status"] == ("met" if mode == "complete" else "needs_review")


async def test_row_drafting_context_preserves_cells_merges_and_reviewed_values(
    session, monkeypatch
):
    import json

    from app.models import (
        AnalysisRun,
        Block,
        FillSuggestion,
        FillTarget,
        ResponseValue,
        TableCell,
    )
    from app.services import suggestions
    from app.services.fill import create_fill_plan, detect_fill_slots

    project, _, _ = await project_config(session)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    await session.flush()
    doc = await document(session, project=project, role="template")
    _, page = await source(session, doc, "设备清单")
    block = Block(
        page_id=page.id, kind="table", reading_order=0, text="设备清单", x0=0, y0=0, x1=600, y1=300
    )
    session.add(block)
    await session.flush()
    cells = []
    for row, values in enumerate([["设备", "规格"], ["水泵", ""], ["风机", ""]]):
        for col, text in enumerate(values):
            cell = TableCell(
                block_id=block.id,
                row_index=row,
                col_index=col,
                row_span=1,
                col_span=1,
                text=text,
                x0=col * 300,
                y0=row * 50,
                x1=(col + 1) * 300,
                y1=(row + 1) * 50,
            )
            session.add(cell)
            cells.append(cell)
    await session.flush()
    session.add(ResponseValue(project_id=project.id, key="spec", label="规格", value_text="通用值"))
    await detect_fill_slots(session, doc)
    plan = await create_fill_plan(
        session, run_id=run.id, project_id=project.id, template_document=doc
    )
    await session.flush()
    targets = list(
        (
            await session.execute(
                select(FillTarget)
                .where(FillTarget.plan_id == plan.id)
                .order_by(FillTarget.created_at)
            )
        ).scalars()
    )
    assert len(targets) == 2
    from app.api.routes import _load_fill_plan

    displayed = await _load_fill_plan(session, plan.id)
    assert "水泵" in displayed.targets[0].location_label
    assert "风机" in displayed.targets[1].location_label
    assert displayed.targets[0].location_label != displayed.targets[1].location_label
    drafts = list(
        (
            await session.execute(
                select(FillSuggestion).where(
                    FillSuggestion.target_id.in_([item.id for item in targets])
                )
            )
        ).scalars()
    )
    assert all(item.value is None for item in drafts)  # Same column label isn't a row binding.
    drafts[0].value = "人工确认水泵规格"
    drafts[0].status = "accepted"
    cells[0].col_span = 2  # Preserve merged-cell geometry in the drafting payload.
    await session.commit()
    seen = []

    async def recall(*args, **kwargs):
        assert "水泵" in kwargs["query"] and "风机" in kwargs["query"]
        return []

    async def draft(*args, **kwargs):
        payload = json.loads(kwargs["user"])
        seen.append(payload)
        assert len(payload["targets"]) == 1
        context = payload["template_context"]
        assert context["existing_values"][0]["value"] == "人工确认水泵规格"
        assert context["existing_values"][0]["status"] == "accepted"
        assert any(cell["col_span"] == 2 for cell in context["cells"])
        target = payload["targets"][0]
        cell = next(item for item in context["cells"] if item["cell_id"] == target["cell_id"])
        assert cell["row"] == 2 and cell["col"] == 1
        return suggestions.Drafts(
            drafts=[
                suggestions.DraftValueItem(
                    target_id=target["target_id"],
                    value="风机规格",
                    evidence_span_ids=[],
                )
            ]
        )

    monkeypatch.setattr(suggestions, "get_settings", lambda: SimpleNamespace(live_model_calls=True))
    monkeypatch.setattr(suggestions, "recall_documents", recall)
    monkeypatch.setattr(suggestions, "structured_text", draft)
    await suggestions.draft_fill_suggestions(session, plan)
    assert len(seen) == 1
    await session.refresh(drafts[0])
    await session.refresh(drafts[1])
    assert drafts[0].value == "人工确认水泵规格" and drafts[0].status == "accepted"
    assert drafts[1].value is None  # Model still cannot invent a value without a source.


async def test_project_and_bid_edits_invalidate_existing_results(session):
    from app.api.routes import update_bid, update_project
    from app.models import AnalysisRun, Decision
    from app.schemas import BidUpdate, ProjectUpdate

    project, _, _ = await project_config(session)
    bid = Bid(project_id=project.id, bidder_name="Acme", lot_code="A")
    run = AnalysisRun(project_id=project.id, status="completed")
    session.add_all([bid, run])
    await session.flush()
    doc = await document(session, project=project, role="tender")
    span, _ = await source(session, doc)
    req = await requirement(session, run, span, "Requirement")
    decision = Decision(run_id=run.id, requirement_id=req.id, status="met", summary="Original")
    session.add(decision)
    await session.commit()
    await update_project(project.id, ProjectUpdate(name="Renamed", tender_no="T-02"), session)
    await session.refresh(decision)
    await session.refresh(run)
    assert decision.stale and run.status == "stale"
    decision.stale = False
    run.status = "completed"
    await session.commit()
    await update_bid(bid.id, BidUpdate(lot_code="B"), session)
    await session.refresh(decision)
    await session.refresh(run)
    assert decision.stale and run.status == "stale"
    assert not (await session.execute(select(Job))).scalars().all()


async def test_shared_material_cannot_enroll_historical_project(session, monkeypatch):
    project, _, _ = await project_config(session)
    await document(session, project=project, role="tender", metadata={"ai_status": "ready"})
    live_pipeline(monkeypatch)
    assert await pipeline.schedule_analysis(session, project, automatic=True) is None
    # Explicitly selecting this project for analysis still works.
    assert await pipeline.schedule_analysis(session, project) is not None


async def fill_workflow(session):
    from app.models import AnalysisRun, AnalysisStatus, Block, FillPlan, TableCell
    from app.services.fill import create_fill_plan, detect_fill_slots

    project, _, _ = await project_config(session)
    template = await document(session, project=project, role="template")
    _, page = await source(session, template)
    run = AnalysisRun(project_id=project.id, status=AnalysisStatus.COMPLETED)
    block = Block(page_id=page.id, kind="table", reading_order=0,
                  x0=100, y0=100, x1=300, y1=300)
    session.add_all([run, block])
    await session.flush()
    cells = [TableCell(block_id=block.id, row_index=row, col_index=0,
                       x0=100, y0=100 + row * 100, x1=300, y1=200 + row * 100)
             for row in range(2)]
    session.add_all(cells)
    await session.flush()
    slots = await detect_fill_slots(session, template)
    for slot in slots:
        slot.label = "规格"
    plan = await create_fill_plan(session, run_id=run.id, project_id=project.id,
                                  template_document=template)
    from app.api.routes import _load_fill_plan

    read = await _load_fill_plan(session, plan.id)
    assert len(read.targets) == 2
    assert isinstance(plan, FillPlan)
    await session.commit()
    return run, plan, read.targets, cells


async def test_analysis_stages_do_not_finish_job_or_validate_unrelated_stale_inputs(
    session, monkeypatch,
):
    from app.models import AnalysisRun, AnalysisStatus, Block
    from app.services.analysis import decide_run
    from app.services.extraction import ExtractedRequirements, extract_requirements_for_run

    project, _, _ = await project_config(session)
    tender = await document(session, project=project, role="tender")
    span, page = await source(session, tender)
    session.add(Block(page_id=page.id, kind="line", reading_order=0, text=page.text,
                      x0=0, y0=0, x1=600, y1=800))
    run = AnalysisRun(project_id=project.id, status=AnalysisStatus.RUNNING)
    session.add(run)
    await session.flush()

    async def extracted(*_args, **_kwargs):
        return ExtractedRequirements()

    monkeypatch.setattr("app.services.extraction._extract_batch", extracted)
    await extract_requirements_for_run(session, run, job_id="offline-job")
    assert run.status == AnalysisStatus.RUNNING
    req = await requirement(session, run, span, "须核对的要求")
    await decide_run(session, run, use_model=False, job_id="offline-job")
    assert run.status == AnalysisStatus.RUNNING
    run.status = AnalysisStatus.STALE
    await decide_run(session, run, use_model=False, requirement_ids={req.id})
    assert run.status == AnalysisStatus.STALE


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_fill_task_blocks_export_and_result_edits(session, status):
    from fastapi import HTTPException

    from app.api.exports import export_bundle
    from app.api.offline import edit_fill_target, remove_fill_target
    from app.api.routes import build_fill_plan, get_report, update_fill_suggestion
    from app.models import JobStatus
    from app.schemas import FillSuggestionUpdate, FillTargetUpdate
    from app.services.jobs import enqueue, request_cancel

    run, plan, targets, _ = await fill_workflow(session)
    job = await enqueue(session, "draft_fill_plan", {"plan_id": plan.id})
    job.status = JobStatus(status)
    plan.status = "queued" if status == "queued" else "drafting"
    await session.commit()
    assert job.payload["run_id"] == run.id
    for call in (
        lambda: export_bundle(run.id, session),
        lambda: get_report(run.id, session),
        lambda: build_fill_plan(run.id, None, session),
        lambda: edit_fill_target(targets[0].id, FillTargetUpdate(label="改名"), session),
        lambda: remove_fill_target(targets[0].id, session),
        lambda: update_fill_suggestion(targets[0].suggestions[0].id,
                                      FillSuggestionUpdate(value="不应保存"), session),
    ):
        with pytest.raises(HTTPException) as exc:
            await call()
        assert exc.value.status_code == 409
    if status == "queued":
        await request_cancel(session, job.id)
        report = await get_report(run.id, session)
        assert "填写起草未完成" in report.markdown
        assert (await export_bundle(run.id, session)).media_type == "application/zip"


async def test_same_label_checklist_requires_each_position_review(session):
    from fastapi import HTTPException

    from app.api.routes import list_checklist, update_checklist, update_fill_suggestion
    from app.models import ChecklistItem
    from app.schemas import ChecklistUpdate, FillSuggestionUpdate
    from app.services.checklist import build_checklist, mark_run_complete_if_ready

    run, plan, targets, _ = await fill_workflow(session)
    session.add(ChecklistItem(run_id=run.id, title="确认填写：规格", completed=True))
    await build_checklist(session, run.id)
    await mark_run_complete_if_ready(session, run.id)
    assert run.status == "needs_review"
    items = await list_checklist(run.id, session)
    assert len(items) == 2
    assert {item.fill_target_id for item in items} == {target.id for target in targets}
    assert all(item.template_document_id == plan.document_id for item in items)
    with pytest.raises(HTTPException) as exc:
        await update_checklist(items[0].id, ChecklistUpdate(completed=True), session)
    assert exc.value.status_code == 409
    await update_fill_suggestion(targets[0].suggestions[0].id,
                                 FillSuggestionUpdate(value="型号 A", status="edited"), session)
    items = await list_checklist(run.id, session)
    assert sum(item.completed for item in items) == 1
    assert run.status == "needs_review"
    await update_fill_suggestion(targets[1].suggestions[0].id,
                                 FillSuggestionUpdate(status="rejected"), session)
    assert run.status == "completed"
    from app.api.exports import export_bundle
    from app.api.routes import get_report

    report = await get_report(run.id, session)
    assert "第 1 行第 1 列" in report.markdown and "第 2 行第 1 列" in report.markdown
    import io
    import zipfile

    bundle = await export_bundle(run.id, session)
    with zipfile.ZipFile(io.BytesIO(bundle.body)) as archive:
        text = archive.read("填写内容清单.csv").decode("utf-8-sig")
        assert "行列位置" in text and "第 2 行第 1 列" in text


async def test_moved_field_rebinds_row_context_and_survives_rebuild(session):
    from app.api.offline import edit_fill_target
    from app.models import FillSlot, FillTarget
    from app.schemas import FillTargetUpdate
    from app.services.fill import rebuild_fill_plan
    from app.services.suggestions import page_drafting_context

    run, plan, targets, cells = await fill_workflow(session)
    first = targets[0]
    await edit_fill_target(first.id, FillTargetUpdate(bbox=[110, 210, 290, 280]), session)
    target = await session.get(FillTarget, first.id)
    slot = await session.get(FillSlot, target.fill_slot_id)
    assert target.table_cell_id == slot.table_cell_id == cells[1].id
    assert slot.locator["row"] == 1
    # Moving out of the table must remove its stale table/cell association.
    await edit_fill_target(first.id, FillTargetUpdate(bbox=[10, 10, 80, 80]), session)
    assert target.table_cell_id is None and target.block_id is None
    assert slot.table_cell_id is None and slot.block_id is None
    await rebuild_fill_plan(session, plan, project_id=run.project_id)
    from sqlalchemy.orm import selectinload

    rebuilt = (await session.execute(
        select(FillTarget).options(selectinload(FillTarget.suggestions))
        .where(FillTarget.fill_slot_id == slot.id)
    )).scalar_one()
    context = await page_drafting_context(session, target.page_id, [rebuilt])
    assert not any(cell["target_id"] == rebuilt.id for cell in context["cells"])
    assert rebuilt.table_cell_id is None


async def test_stale_hand_edited_values_survive_relocation(session):
    from app.api.routes import build_fill_plan, update_fill_suggestion
    from app.schemas import FillSuggestionUpdate
    from app.services.freshness import mark_project_stale

    run, _plan, targets, _cells = await fill_workflow(session)
    await update_fill_suggestion(
        targets[0].suggestions[0].id,
        FillSuggestionUpdate(value="人工校正型号", status="edited"), session,
    )
    await mark_project_stale(session, run.project_id)
    rebuilt = await build_fill_plan(run.id, None, session)
    preserved = next(t for t in rebuilt.targets if t.suggestions[0].value == "人工校正型号")
    assert preserved.suggestions[0].status == "proposed"
    assert preserved.suggestions[0].reviewed_at is not None
    assert run.status == "stale"
