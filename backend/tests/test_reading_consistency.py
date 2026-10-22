"""The reading, review, checklist and exported artifacts share persisted source data."""
import asyncio
import csv
import io
import json
import zipfile
from collections import Counter

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_automatic_recovery import setup_customer
from test_complete_workflow import checked, stub_models
from test_end_to_end import _run_worker_until

from app.db import get_engine
from app.main import app
from app.models import AnalysisRun
from app.services import model_gateway
from app.services.model_gateway import ModelGatewayError


async def test_confirmed_amendment_rebinds_fields_and_reopens_checks(session):
    from test_workflow_gaps import document, fill_workflow, requirement, source

    from app.api.routes import update_requirement
    from app.models import Decision, FillTarget, Project
    from app.schemas import RequirementUpdate
    from app.services.checklist import build_checklist

    run, plan, targets, _ = await fill_workflow(session)
    project = await session.get(Project, run.project_id)
    base = await document(session, project=project, role="tender")
    span, _ = await source(session, base, "金额500万元，更正为300万元")
    old = await requirement(session, run, span, "金额500万元")
    new = await requirement(session, run, span, "金额300万元")
    session.add_all([Decision(run_id=run.id, requirement_id=req.id, status="needs_review",
                              summary="待核对金额")
                     for req in (old, new)])
    target = await session.get(FillTarget, targets[0].id)
    target.requirement_id = old.id
    await build_checklist(session, run.id)
    await update_requirement(new.id, RequirementUpdate(
        supersedes_ids=[old.id], version_confirmed=True,
    ), session)
    await session.refresh(target)
    await session.refresh(plan)
    assert target.requirement_id == new.id and plan.status == "stale"
    checks = await build_checklist(session, run.id)
    item = next(c for c in checks if c.fill_target_id == target.id)
    assert item.requirement_id == new.id and not item.completed


def assert_delivery(client, run_url):
    decisions = checked(client.get(run_url + "/decisions"))
    report = checked(client.get(run_url + "/report"))
    assert {key: count for key, count in report["summary"].items() if count} == dict(
        Counter(row["status"] for row in decisions)
    )
    plan = checked(client.get(run_url + "/fill-plan"))
    checklist = checked(client.get(run_url + "/checklist"))
    fill_checks = {row["fill_target_id"]: row for row in checklist if row["fill_target_id"]}
    bundle = client.get(run_url + "/export")
    assert bundle.is_success, bundle.text
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        csv_text = archive.read("填写内容清单.csv").decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        annotations = {row["target_id"]: row for asset in plan["assets"]
                       for row in asset["annotations"]}
        assert len(rows) == len(plan["targets"]) == len(fill_checks)
        for target in plan["targets"]:
            suggestion = target["suggestions"][0]
            expected = "未采用" if suggestion["status"] == "rejected" else suggestion["value"] or ""
            row = next(row for row in rows if row["填写位置"] == target["label"])
            assert row["填写内容"] == expected
            assert annotations[target["id"]]["value"] == expected
            assert annotations[target["id"]]["status"] == suggestion["status"]
            assert fill_checks[target["id"]]["completed"] == (
                suggestion["status"] in {"accepted", "edited", "rejected"}
            )
        pngs = [archive.read(name) for name in archive.namelist() if name.endswith(".png")]
        for asset in plan["assets"]:
            assert client.get(f"/api/v2/annotation-assets/{asset['id']}/image").content in pngs
        return archive.read("投标准备检查报告.md").decode(), rows


def test_requirement_edits_and_failed_run_updates_reopen_all_deliverables(
    empty_table_pdf, monkeypatch,
):
    stub_models(monkeypatch)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        project_url = f"/api/v2/projects/{project['id']}"
        checked(client.patch(project_url, json={"auto_analyze": False}))
        asyncio.run(_run_worker_until(client, project["id"]))
        run = checked(client.post(project_url + "/analysis-runs", json={"mode": "model"}))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        run_url = f"/api/v2/analysis-runs/{run['id']}"
        plan = checked(client.get(run_url + "/fill-plan"))
        for target in plan["targets"]:
            checked(client.patch(f"/api/v2/fill-suggestions/{target['suggestions'][0]['id']}",
                                 json={"value": "Retained human value", "status": "edited"}))
        checked(client.patch(f"/api/v2/fill-suggestions/{plan['targets'][0]['suggestions'][0]['id']}",
                             json={"status": "rejected"}))
        report, rows = assert_delivery(client, run_url)
        assert rows[0]["填写内容"] == "未采用" and "内容：未采用" in report
        requirement = checked(client.get(run_url + "/requirements"))[0]
        checked(client.patch(f"/api/v2/requirements/{requirement['id']}", json={
            "statement": "ISO9001 certificate required with additional scope",
        }))
        changed = checked(client.get(run_url + "/fill-plan"))
        assert changed["status"] == "stale"
        assert all(t["suggestions"][0]["status"] == "proposed" for t in changed["targets"])
        report, _ = assert_delivery(client, run_url)
        assert "填写建议及标注图需重新核对" in report
        for target in changed["targets"]:
            checked(client.patch(f"/api/v2/fill-suggestions/{target['suggestions'][0]['id']}",
                                 json={"status": "accepted"}))

        async def fail():
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                stored = await session.get(AnalysisRun, run["id"])
                stored.status = "failed"
                await session.commit()

        asyncio.run(fail())
        checked(client.patch(project_url, json={"bidder_name": "Updated bidder"}))
        assert checked(client.get(run_url))["status"] == "failed"
        assert all(d["stale"] for d in checked(client.get(run_url + "/decisions")))
        assert all(t["suggestions"][0]["status"] == "proposed"
                   for t in checked(client.get(run_url + "/fill-plan"))["targets"])
        report, _ = assert_delivery(client, run_url)
        assert "分析未完成" in report and "待重新核对" in report


def reading_stub(monkeypatch):
    calls = stub_models(monkeypatch)
    original = model_gateway.complete_text

    async def with_reading(session, *, user, purpose, **kwargs):
        result = await original(session, user=user, purpose=purpose, **kwargs)
        if purpose == "extract_requirements":
            data = json.loads(user[user.index("{"):])
            block = next(b for b in data["blocks"] if "ISO9001" in b["text"])
            result = json.loads(result)
            result["reading_items"] = [{
                "section": "overview", "title": "采购范围", "content": "ISO9001",
                "block_id": block["block_id"], "quote": "ISO9001",
            }, {"section": "timeline", "title": "编造日期", "content": "2099-01-01",
                "block_id": block["block_id"], "quote": "not present in source"}]
            return json.dumps(result)
        return result

    monkeypatch.setattr(model_gateway, "complete_text", with_reading)
    return calls


def test_tender_reading_without_company_reuses_extraction_and_rejects_invalid_sources(monkeypatch):
    calls = reading_stub(monkeypatch)
    with TestClient(app) as client:
        checked(client.post("/api/v2/model-configs", json={
            "name": "Stub", "base_url": "https://offline.invalid/v1", "api_key": "fixture",
            "text_model": "stub", "embedding_model": "stub",
        }))
        project = checked(client.post("/api/v2/projects", json={"name": "Source-backed reading"}))
        url = f"/api/v2/projects/{project['id']}"
        checked(client.post(url + "/documents", data={"role": "tender"}, files={"file": (
            "tender.csv", b"requirement\nISO9001 certificate required\n", "text/csv",
        )}))
        asyncio.run(_run_worker_until(client, project["id"]))
        reading = checked(client.get(url + "/interpretation"))
        assert reading["run_id"] is None and not reading["pending_documents"]
        by_section = {section["key"]: section["items"] for section in reading["sections"]}
        assert by_section["overview"][0]["source_span"]["quote"] == "ISO9001"
        assert by_section["qualification"] and not by_section["timeline"]
        export = client.get(url + "/interpretation/export").text
        assert "tender.csv · 第 1 页" in export and "2099" not in export
        before = len(calls)
        checked(client.get(url + "/interpretation"))
        client.get(url + "/interpretation/export")
        assert len(calls) == before
        manual = checked(client.post(url + "/analysis-runs", json={"mode": "manual"}))
        with_manual = checked(client.get(url + "/interpretation"))
        assert with_manual["run_id"] == manual["id"]
        assert next(s for s in with_manual["sections"]
                    if s["key"] == "qualification")["items"]
        checked(client.post(url + "/documents", data={"role": "addendum"}, files={"file": (
            "amended.csv", b"requirement\nISO9001 amended requirement\n", "text/csv",
        )}))
        updated = checked(client.get(url + "/interpretation"))
        assert updated["amendments_pending"] and updated["pending_documents"]
        asyncio.run(_run_worker_until(client, project["id"]))
        assert checked(client.get(url + "/interpretation"))["amendments_pending"]
        assert len(checked(client.get(url + "/analysis-runs"))) == 1
        from app.config import get_settings

        monkeypatch.setenv("TENDER_LIVE_MODEL_CALLS", "false")
        get_settings.cache_clear()
        before = len(calls)
        assert client.post(url + "/interpretation").status_code == 409
        assert len(calls) == before


def test_resumed_draft_and_reading_match_the_final_bundle(empty_table_pdf, monkeypatch):
    reading_stub(monkeypatch)
    original = model_gateway.complete_text
    failed = []

    async def interrupted(session, *, purpose, **kwargs):
        if purpose == "draft_fill_values" and not failed:
            failed.append(1)
            raise ModelGatewayError("Injected draft interruption")
        return await original(session, purpose=purpose, **kwargs)

    monkeypatch.setattr(model_gateway, "complete_text", interrupted)
    with TestClient(app) as client:
        project, _ = setup_customer(client, empty_table_pdf)
        url = f"/api/v2/projects/{project['id']}"
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        run = checked(client.get(url + "/analysis-runs"))[0]
        run_url = f"/api/v2/analysis-runs/{run['id']}"
        assert run["status"] == "failed"
        checked(client.post(run_url + "/resume"))
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        assert_delivery(client, run_url)
        reading = checked(client.get(url + "/interpretation"))
        assert reading["run_id"] == run["id"]
        row = next(s for s in reading["sections"] if s["key"] == "qualification")["items"][0]
        decision = checked(client.get(run_url + "/decisions"))[0]
        assert row["requirement_id"] == decision["requirement_id"]
        assert row["decision_status"] == decision["status"]
