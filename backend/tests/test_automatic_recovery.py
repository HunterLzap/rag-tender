"""Automatic workflow recovery at the real queue boundaries, with no external HTTP."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_complete_workflow import checked, stub_models
from test_end_to_end import _run_worker_until
from test_workflow_gaps import document, fill_workflow, live_pipeline, project_config, source

from app.main import app
from app.models import (
    AnalysisRun,
    AnalysisStatus,
    Document,
    FillSlot,
    FillSuggestion,
    FillTarget,
    Job,
    JobStatus,
    Page,
    Project,
)
from app.services import pipeline, suggestions
from app.services.jobs import _process_one
from app.services.model_gateway import ModelGatewayError


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    async def blocked(*_args, **_kwargs):
        raise AssertionError("External HTTP is forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)


@pytest.mark.parametrize("terminal", [JobStatus.FAILED, JobStatus.CANCELED])
async def test_startup_dispatches_ready_inputs_without_retrying_terminal_jobs(
    session, monkeypatch, terminal,
):
    project, _, organization = await project_config(session)
    await document(session, project=project, role="tender",
                   metadata={"ai_status": "ready", "auto_process": True})
    await document(session, organization=organization, metadata={
        "ai_status": "pending", "auto_process": True, "parse_status": "canceled",
    })
    live_pipeline(monkeypatch)
    assert await pipeline.resume_pending_documents(session) == 0
    job = (await session.execute(select(Job))).scalar_one()
    run = await session.get(AnalysisRun, job.payload["run_id"])
    assert await pipeline.resume_pending_documents(session) == 0
    assert len((await session.execute(select(Job))).scalars().all()) == 1
    job.status = terminal
    run.status = AnalysisStatus.FAILED
    await session.commit()
    await pipeline.resume_pending_documents(session)
    assert len((await session.execute(select(Job))).scalars().all()) == 1
    resumed = await pipeline.resume_analysis(session, run)
    assert resumed.payload["resume"] and resumed.payload["run_id"] == run.id
    resumed.status = terminal
    run.status = AnalysisStatus.FAILED
    project.name = "Changed inputs"
    await session.flush()
    with pytest.raises(ModelGatewayError, match="资料或模型配置已变化"):
        await pipeline.resume_analysis(session, run)


@pytest.mark.parametrize("change_inputs", [False, True])
async def test_draft_resume_keeps_completed_pages_unless_inputs_change(
    session, monkeypatch, change_inputs,
):
    from app.api.library import draft_fill_plan

    run, plan, targets, _ = await fill_workflow(session)
    template = await session.get(Document, plan.document_id)
    page = Page(document_id=template.id, revision_id=template.current_revision_id,
                page_index=1, width=600, height=800, text="Second page")
    session.add(page)
    await session.flush()
    target = FillTarget(plan_id=plan.id, page_id=page.id, label="第二页字段",
                        kind="text_box", bbox_json=[10, 10, 100, 40])
    session.add(target)
    await session.flush()
    session.add(FillSuggestion(target_id=target.id, value=None, rationale="未起草",
                               status="missing_evidence"))
    project = await session.get(Project, run.project_id)
    config = await pipeline.pipeline_config(session)
    signature = (await pipeline.project_inputs(session, project, config))[2]
    job = Job(kind="draft_fill_plan", status=JobStatus.RUNNING, attempts=1, max_attempts=1,
              payload={"plan_id": plan.id, "model_config_id": config.id,
                       "project_id": project.id, "input_signature": signature})
    session.add(job)
    await session.commit()
    second_page_id = page.id
    calls = []

    async def recall(*_args, **_kwargs):
        return []

    async def draft(*_args, **kwargs):
        data = json.loads(kwargs["user"])
        current = data["template_context"]["page_id"]
        calls.append(current)
        if current == second_page_id and calls.count(current) == 1:
            raise ModelGatewayError("offline injected second-page failure")
        return suggestions.Drafts(drafts=[suggestions.DraftValueItem(
            target_id=item["target_id"], value=None, rationale="本页已核验，缺少事实",
        ) for item in data["targets"]])

    monkeypatch.setattr(suggestions, "get_settings", lambda: SimpleNamespace(live_model_calls=True))
    monkeypatch.setattr("app.api.library.get_settings",
                        lambda: SimpleNamespace(live_model_calls=True))
    monkeypatch.setattr(suggestions, "recall_documents", recall)
    monkeypatch.setattr(suggestions, "structured_text", draft)
    await _process_one(session, job)
    await session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.result["drafted_pages"][plan.id][targets[0].page_id]
    if change_inputs:
        project.name = "Changed project"
        await session.commit()
    resumed = await draft_fill_plan(plan.id, session)
    resumed.status = JobStatus.RUNNING
    resumed.attempts = 1
    await session.commit()
    await _process_one(session, resumed)
    await session.refresh(resumed)
    assert resumed.status == JobStatus.COMPLETED, resumed.error
    assert calls.count(targets[0].page_id) == (2 if change_inputs else 1)
    assert calls.count(second_page_id) == 2


async def test_scan_label_resume_does_not_repeat_finished_pages(session, monkeypatch):
    from app.services.handlers import _label_scanned_slots

    project, _, _ = await project_config(session)
    template = await document(session, project=project, role="template")
    _, first = await source(session, template)
    first.render_path = "unused.png"
    second = Page(document_id=template.id, revision_id=template.current_revision_id,
                  page_index=1, width=600, height=800, render_path="unused.png")
    session.add(second)
    await session.flush()
    slots = [FillSlot(template_revision_id=template.current_revision_id, page_id=page.id,
                      kind="table_cell", label="未命名", bbox_json=[1, 1, 100, 50],
                      locator={"coordinate_quality": "scan_lines"}) for page in (first, second)]
    session.add_all(slots)
    await session.commit()
    calls = []

    async def labels(*_args, **kwargs):
        data = json.loads(kwargs["user"])
        slot_id = data["slots"][0]["slot_id"]
        calls.append(slot_id)
        if slot_id == slots[1].id and calls.count(slot_id) == 1:
            raise ModelGatewayError("offline scan label failure")
        return SimpleNamespace(labels=[SimpleNamespace(slot_id=slot_id, label="字段名称")])

    monkeypatch.setattr("app.services.model_gateway.structured_text", labels)
    job = SimpleNamespace(id=None, payload={"model_config_id": "unused"})
    with pytest.raises(ModelGatewayError):
        await _label_scanned_slots(session, template, job)
    await _label_scanned_slots(session, template, job)
    assert calls == [slots[0].id, slots[1].id, slots[1].id]


def setup_customer(client, pdf):
    checked(client.post("/api/v2/model-configs", json={
        "name": "Stub", "base_url": "https://offline.invalid/v1", "api_key": "fixture",
        "text_model": "stub", "embedding_model": "stub",
    }))
    org = checked(client.post("/api/v2/organizations", json={"name": "Acme"}))
    checked(client.post(f"/api/v2/organizations/{org['id']}/documents", files={"file": (
        "proof.csv", b"certificate,holder,valid_until\nISO9001,Acme,2028-12-31\n", "text/csv",
    )}))
    project = checked(client.post("/api/v2/projects", json={
        "name": "Resume fixture", "organization_id": org["id"], "bidder_name": "Acme",
    }))
    for role, name, content in [
        ("tender", "tender.csv", b"requirement\nISO9001 certificate required\n"),
        ("template", "template.pdf", pdf.read_bytes()),
    ]:
        checked(client.post(f"/api/v2/projects/{project['id']}/documents", data={"role": role},
                            files={"file": (name, content, "application/octet-stream")}))
    return project, org


def test_analysis_continues_same_run_and_keeps_completed_comparisons(empty_table_pdf, monkeypatch):
    from app.services import model_gateway

    stub_models(monkeypatch)
    original = model_gateway.complete_text
    compares = []
    drafts = []

    async def interrupted(session, *, user, purpose, **kwargs):
        if purpose == "compare_requirement":
            compares.append(json.loads(user)["requirement"])
            if len(compares) == 2:
                raise ModelGatewayError("offline comparison failure")
        result = await original(session, user=user, purpose=purpose, **kwargs)
        if purpose == "extract_requirements":
            data = json.loads(result)
            data["requirements"].append({**data["requirements"][0],
                                         "statement": "ISO9001 additional requirement"})
            result = json.dumps(data)
        if purpose == "draft_fill_values":
            drafts.append(1)
            if len(drafts) == 1:
                result = '{"drafts":[]}'  # A missing field must fail visibly, not silently finish.
        return result

    monkeypatch.setattr(model_gateway, "complete_text", interrupted)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        run = checked(client.get(project_url + "/analysis-runs"))[0]
        run_url = f"/api/v2/analysis-runs/{run['id']}"
        assert run["status"] == "failed"
        saved = checked(client.get(run_url + "/decisions"))
        assert len(saved) == 1
        checked(client.post(f"/api/v2/decisions/{saved[0]['id']}/reviews", json={
            "new_status": "met", "reason": "人工复核保留样例",
        }))
        checked(client.post(run_url + "/resume"))
        assert checked(client.get(run_url))["progress"] == 0
        assert client.post(run_url + "/resume").status_code == 409
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        assert checked(client.get(run_url))["status"] == "failed"
        assert "遗漏" in checked(client.get(run_url))["error"]
        assert len(compares) == 3  # First persisted comparison wasn't called again.
        plan = checked(client.get(run_url + "/fill-plan"))
        target = plan["targets"][0]
        checked(client.patch(f"/api/v2/fill-suggestions/{target['suggestions'][0]['id']}",
                             json={"value": "人工确认值", "status": "edited"}))
        checked(client.post(run_url + "/resume"))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        assert checked(client.get(run_url))["status"] == "needs_review"
        assert len(checked(client.get(project_url + "/analysis-runs"))) == 1
        assert len(compares) == 3
        refreshed = checked(client.get(run_url + "/fill-plan"))
        assert refreshed["id"] == plan["id"]
        assert refreshed["targets"][0]["id"] == target["id"]
        assert refreshed["targets"][0]["suggestions"][0]["value"] == "人工确认值"
        assert any(d["summary"] == "人工复核保留样例"
                   for d in checked(client.get(run_url + "/decisions")))
        assert client.get(run_url + "/export").status_code == 200


def test_material_embedding_failure_continues_without_reextracting(empty_table_pdf, monkeypatch):
    from app.services import library

    calls = stub_models(monkeypatch)
    original = library.embed_texts
    failed = []

    async def broken_once(*args, **kwargs):
        if not failed:
            failed.append(1)
            raise ModelGatewayError("offline embedding failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(library, "embed_texts", broken_once)
    with TestClient(app) as client:
        project, org = setup_customer(client, empty_table_pdf)
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        proof_url = f"/api/v2/organizations/{org['id']}/documents"
        proof = checked(client.get(proof_url))[0]
        assert proof["ai_status"] == "failed"
        assert calls.count("extract_enterprise_material") == 1
        previous = checked(client.get(f"/api/v2/projects/{project['id']}/evidence"))
        checked(client.post(f"/api/v2/documents/{proof['id']}/process"))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        assert checked(client.get(proof_url))[0]["ai_status"] == "ready"
        evidence = checked(client.get(f"/api/v2/projects/{project['id']}/evidence"))
        assert [e["id"] for e in evidence] == [e["id"] for e in previous]
        assert calls.count("extract_enterprise_material") == 1
        runs = checked(client.get(f"/api/v2/projects/{project['id']}/analysis-runs"))
        assert len(runs) == 2 and runs[0]["status"] == "needs_review"
        assert "stale" in {r["status"] for r in runs[1:]}


async def test_input_signature_is_stable_after_datetime_reload(session):
    from datetime import UTC, datetime

    from app.models import Bid

    project, config, organization = await project_config(session)
    project.bid_deadline = datetime(2027, 1, 5, 1, tzinfo=UTC)
    bid = Bid(project_id=project.id, bidder_name="Acme", bid_deadline=project.bid_deadline)
    session.add(bid)
    await session.flush()
    before = (await pipeline.project_inputs(session, project, config))[2]
    await session.refresh(project)
    await session.refresh(bid)
    await session.refresh(organization)
    assert (await pipeline.project_inputs(session, project, config))[2] == before
