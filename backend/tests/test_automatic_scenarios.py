"""Concurrent input changes and interruption scenarios; all external HTTP is blocked."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_automatic_recovery import setup_customer
from test_complete_workflow import checked, stub_models
from test_end_to_end import _run_worker_until
from test_reading_consistency import assert_delivery

from app.db import get_engine
from app.main import app
from app.models import AnalysisRun, Job, JobStatus
from app.services import handlers, model_gateway, pipeline
from app.worker import fail_running_jobs


def test_parallel_uploads_and_amendment_reach_updated_fill(empty_table_pdf, monkeypatch):
    calls = stub_models(monkeypatch)
    original = model_gateway.complete_text
    drafted_requirements = []

    async def amended(session, *, user, purpose, **kwargs):
        data = json.loads(user[user.index("{"):])
        if purpose == "resolve_requirement_versions":
            return json.dumps({"relations": [{
                "prior_id": old["id"], "relation": "replaces", "reason": "明确修订",
                "prior_quote": old["quote"], "amendment_quote": data["amendment"]["quote"],
            } for old in data["prior"]]})
        if purpose == "draft_fill_values":
            drafted_requirements.append(data["requirements"])
        result = await original(session, user=user, purpose=purpose, **kwargs)
        if purpose == "extract_requirements":
            result_data = json.loads(result)
            item = result_data["requirements"][0]
            if any("amended" in block["text"] for block in data["blocks"]):
                item["statement"] = "ISO9001 amended certificate required"
                item["quote"] = "ISO9001 amended certificate required"
            elif any("supplementary" in block["text"] for block in data["blocks"]):
                item["statement"] = "ISO9001 supplementary requirement"
            return json.dumps(result_data)
        return result

    monkeypatch.setattr(model_gateway, "complete_text", amended)
    with TestClient(app) as client:
        project, org = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        uploads = [
            (project_url + "/documents", {"role": "tender"}, "second.csv",
             b"requirement\nISO9001 supplementary requirement\n"),
            (f"/api/v2/organizations/{org['id']}/documents", {}, "second-proof.csv",
             b"certificate,holder\nISO9001,Acme,second\n"),
        ]

        def upload(item):
            url, data, name, content = item
            return checked(client.post(url, data=data, files={"file": (name, content, "text/csv")}))

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert len(list(pool.map(upload, uploads))) == 2
        asyncio.run(_run_worker_until(client, project["id"], expected_documents=3,
                                      expected_runs=True))
        runs = checked(client.get(project_url + "/analysis-runs"))
        assert runs[0]["status"] == "needs_review"
        assert all(run["status"] == "stale" for run in runs[1:])
        initial_runs = len(runs)
        assert len(checked(client.get(project_url + "/evidence"))) == 2
        before = calls.count("extract_requirements")
        upload((project_url + "/documents", {"role": "addendum"}, "amendment.csv",
                b"requirement\nISO9001 amended certificate required\n"))
        asyncio.run(_run_worker_until(client, project["id"], expected_documents=4,
                                      expected_runs=True))
        runs = checked(client.get(project_url + "/analysis-runs"))
        assert len(runs) == initial_runs + 1
        assert runs[0]["status"] == "needs_review" and runs[1]["status"] == "stale"
        assert calls.count("extract_requirements") == before + 1
        decisions = checked(client.get(f"/api/v2/analysis-runs/{runs[0]['id']}/decisions"))
        assert sum(d["status"] == "not_applicable" for d in decisions) == 2
        assert len(drafted_requirements[-1]) == 1
        assert drafted_requirements[-1][0]["statement"] == "ISO9001 amended certificate required"
        assert checked(client.get(f"/api/v2/analysis-runs/{runs[0]['id']}/fill-plan"))["assets"]
        assert_delivery(client, f"/api/v2/analysis-runs/{runs[0]['id']}")
        reading = checked(client.get(project_url + "/interpretation"))
        assert reading["run_id"] == runs[0]["id"] and not reading["amendments_pending"]
        qualification = next(s for s in reading["sections"] if s["key"] == "qualification")
        assert sum(row["state"] == "superseded" for row in qualification["items"]) == 2


@pytest.mark.parametrize("change", ["project", "response_value"])
def test_edit_during_final_draft_invalidates_old_run_and_dispatches_new(
    empty_table_pdf, monkeypatch, change,
):
    stub_models(monkeypatch)
    original = model_gateway.complete_text
    edits = []

    async def changed(session, *, user, purpose, **kwargs):
        if purpose == "draft_fill_values" and not edits:
            # The draft has already loaded Project and ResponseValue in its identity map.
            edits.append(1)
            if change == "project":
                checked(client.patch(project_url, json={"name": "Updated during processing"}))
            else:
                checked(client.patch(f"/api/v2/response-values/{value['id']}",
                                     json={"value_text": "Updated equipment"}))
        return await original(session, user=user, purpose=purpose, **kwargs)

    monkeypatch.setattr(model_gateway, "complete_text", changed)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        value = checked(client.post(project_url + "/response-values", json={
            "key": "equipment", "label": "Equipment", "value_text": "Original equipment",
            "review_status": "verified",
        }))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        runs = checked(client.get(project_url + "/analysis-runs"))
        assert len(runs) == 2, runs
        assert runs[0]["status"] == "needs_review" and runs[1]["status"] == "stale"
        assert edits == [1]
        if change == "response_value":
            plan = checked(client.get(f"/api/v2/analysis-runs/{runs[0]['id']}/fill-plan"))
            assert any(t["suggestions"][0]["value"] == "Updated equipment" for t in plan["targets"])


def test_cancel_during_parse_does_not_enqueue_ai_and_stays_canceled_after_restart(
    empty_table_pdf, monkeypatch,
):
    calls = stub_models(monkeypatch)
    original = handlers.persist_parsed_document
    canceled_ids = []

    async def canceled(session, document, parsed):
        if document.role == "tender":
            jobs = checked(client.get(project_url + "/jobs"))
            job = next(j for j in jobs if j["payload"].get("document_id") == document.id
                       and j["kind"] == "parse_document")
            checked(client.post(f"/api/v2/jobs/{job['id']}/cancel"))
            canceled_ids.append(document.id)
        return await original(session, document, parsed)

    monkeypatch.setattr(handlers, "persist_parsed_document", canceled)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        asyncio.run(_run_worker_until(client, project["id"]))
        jobs = checked(client.get(project_url + "/jobs"))
        tender_jobs = [j for j in jobs if j["payload"].get("document_id") in canceled_ids]
        assert [j["kind"] for j in tender_jobs] == ["parse_document"]
        assert tender_jobs[0]["status"] == "canceled"

        async def restart():
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                await fail_running_jobs(session)
                await pipeline.resume_pending_documents(session)
                await session.commit()

        asyncio.run(restart())
        asyncio.run(_run_worker_until(client, project["id"]))
        assert not checked(client.get(project_url + "/analysis-runs"))
        assert "extract_requirements" not in calls


@pytest.mark.parametrize("kind", ["parse_document", "analyze_project"])
async def test_cancel_requested_at_crash_is_terminal_on_restart(session, kind):
    run = AnalysisRun(project_id="fixture", status="running")
    session.add(run)
    await session.flush()
    job = Job(kind=kind, payload={"run_id": run.id, "document_id": "missing"},
              status=JobStatus.RUNNING,
              attempts=1, max_attempts=3 if kind == "parse_document" else 1,
              cancel_requested=True)
    session.add(job)
    await session.commit()
    await fail_running_jobs(session)
    await session.refresh(job)
    assert job.status == JobStatus.CANCELED
    assert job.finished_at and not job.lease_owner
    if kind == "analyze_project":
        await session.refresh(run)
        assert run.stage == "analysis_canceled"


@pytest.mark.parametrize("purpose_to_cancel", ["compare_requirement", "draft_fill_values"])
def test_cancel_running_analysis_stops_next_stage_until_explicit_resume(
    empty_table_pdf, monkeypatch, purpose_to_cancel,
):
    calls = stub_models(monkeypatch)
    original = model_gateway.complete_text
    cancellations = []

    async def canceled(session, *, purpose, **kwargs):
        if purpose == purpose_to_cancel and not cancellations:
            cancellations.append(1)
            jobs = checked(client.get(project_url + "/jobs"))
            job = next(j for j in jobs if j["kind"] == "analyze_project"
                       and j["status"] == "running")
            checked(client.post(f"/api/v2/jobs/{job['id']}/cancel"))
        return await original(session, purpose=purpose, **kwargs)

    monkeypatch.setattr(model_gateway, "complete_text", canceled)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        run = checked(client.get(project_url + "/analysis-runs"))[0]
        assert run["stage"] == "analysis_canceled"
        if purpose_to_cancel == "compare_requirement":
            assert "draft_fill_values" not in calls
        call_count = len(calls)

        async def restart():
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                await fail_running_jobs(session)
                await pipeline.resume_pending_documents(session)
                await session.commit()

        asyncio.run(restart())
        asyncio.run(_run_worker_until(client, project["id"]))
        assert len(calls) == call_count
        checked(client.post(f"/api/v2/analysis-runs/{run['id']}/resume"))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        runs = checked(client.get(project_url + "/analysis-runs"))
        assert len(runs) == 1 and runs[0]["status"] == "needs_review"


def test_restart_interrupted_analysis_preserves_saved_comparisons(empty_table_pdf, monkeypatch):
    stub_models(monkeypatch)
    original = model_gateway.complete_text
    comparisons = []

    async def interrupted(session, *, user, purpose, **kwargs):
        if purpose == "compare_requirement":
            comparisons.append(1)
            if len(comparisons) == 2:
                raise asyncio.CancelledError("Simulated process interruption")
        result = await original(session, user=user, purpose=purpose, **kwargs)
        if purpose == "extract_requirements":
            data = json.loads(result)
            data["requirements"].append({**data["requirements"][0],
                                         "statement": "Additional ISO9001 requirement"})
            return json.dumps(data)
        return result

    monkeypatch.setattr(model_gateway, "complete_text", interrupted)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(_run_worker_until(client, project["id"]))
        run = checked(client.get(project_url + "/analysis-runs"))[0]
        run_url = f"/api/v2/analysis-runs/{run['id']}"
        assert len(checked(client.get(run_url + "/decisions"))) == 1

        async def restart():
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                await fail_running_jobs(session)
                await pipeline.resume_pending_documents(session)
                await session.commit()

        asyncio.run(restart())
        assert checked(client.get(run_url))["status"] == "failed"
        checked(client.post(run_url + "/resume"))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        assert checked(client.get(run_url))["status"] == "needs_review"
        assert len(comparisons) == 3
        assert len(checked(client.get(project_url + "/analysis-runs"))) == 1


def test_edit_during_separate_draft_leaves_plan_stale(empty_table_pdf, monkeypatch):
    stub_models(monkeypatch)
    original = model_gateway.complete_text
    armed = []

    async def changed(session, *, purpose, **kwargs):
        if purpose == "draft_fill_values" and armed:
            armed.clear()
            checked(client.patch(project_url, json={"name": "Changed during separate draft"}))
        return await original(session, purpose=purpose, **kwargs)

    monkeypatch.setattr(model_gateway, "complete_text", changed)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        run = checked(client.get(project_url + "/analysis-runs"))[0]
        run_url = f"/api/v2/analysis-runs/{run['id']}"
        plan = checked(client.get(run_url + "/fill-plan"))
        checked(client.patch(project_url, json={"auto_analyze": False}))
        armed.append(1)
        checked(client.post(f"/api/v2/fill-plans/{plan['id']}/draft"))
        asyncio.run(_run_worker_until(client, project["id"]))
        assert checked(client.get(run_url))["status"] == "stale"
        assert checked(client.get(run_url + "/fill-plan"))["status"] == "stale"
