import asyncio
import io
import zipfile

from fastapi.testclient import TestClient
from test_end_to_end import _run_worker_until

from app.main import app


def prepare(client, source, roles):
    project = client.post("/api/v2/projects", json={"name": "Offline workflow fixture"}).json()
    documents = []
    for role in roles:
        response = client.post(
            f"/api/v2/projects/{project['id']}/documents",
            data={"role": role},
            files={"file": ("fixture.pdf", source.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 201, response.text
        documents.append(response.json())
    asyncio.run(_run_worker_until(client, project["id"], expected_documents=len(roles)))
    response = client.post(
        f"/api/v2/projects/{project['id']}/analysis-runs", json={"mode": "manual"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["model_snapshot"] == {"execution_mode": "manual"}
    assert not any(
        job["kind"] == "analyze_project"
        for job in client.get(f"/api/v2/projects/{project['id']}/jobs").json()
    )
    return project, documents, response.json()


def test_manual_requirements_reviews_and_source_freshness(empty_table_pdf, monkeypatch):
    async def reject_network(*_args, **_kwargs):
        raise AssertionError("Offline workflow attempted a model request")

    monkeypatch.setattr("httpx.AsyncClient.post", reject_network)
    with TestClient(app) as client:
        project, documents, run = prepare(client, empty_table_pdf, ["tender", "evidence"])
        project_id, run_id = project["id"], run["id"]
        page = client.get(f"/api/v2/documents/{documents[0]['id']}/pages").json()[0]
        span = client.get(f"/api/v2/pages/{page['id']}/source-spans").json()[0]
        requirements = []
        for statement in ("First requirement", "Second requirement"):
            response = client.post(
                f"/api/v2/analysis-runs/{run_id}/requirements",
                json={
                    "title": "Same title", "statement": statement, "source_span_id": span["id"],
                },
            )
            assert response.status_code == 201, response.text
            requirements.append(response.json())
        items = client.get(f"/api/v2/analysis-runs/{run_id}/checklist").json()
        assert len([item for item in items if item["title"] == "Same title"]) == 2
        decisions = client.get(f"/api/v2/analysis-runs/{run_id}/decisions").json()
        first = next(item for item in decisions if item["requirement_id"] == requirements[0]["id"])
        reviewed = client.post(
            f"/api/v2/decisions/{first['id']}/reviews",
            json={"new_status": "met", "reason": "Checked source", "evidence_ids": []},
        )
        assert reviewed.status_code == 201, reviewed.text
        edited = client.patch(
            f"/api/v2/requirements/{requirements[0]['id']}",
            json={"statement": "Changed requirement"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["source_span"]["quote"]
        items = client.get(f"/api/v2/analysis-runs/{run_id}/checklist").json()
        assert not next(
            item for item in items if item["requirement_id"] == requirements[0]["id"]
        )["completed"]
        deadline = client.patch(
            f"/api/v2/projects/{project_id}", json={"bid_deadline": "2027-02-01T00:30:00+08:00"},
        )
        assert deadline.json()["bid_deadline"] == "2027-01-31T16:30:00Z"
        assert client.get(f"/api/v2/analysis-runs/{run_id}").json()["status"] == "stale"
        rechecked = client.post(f"/api/v2/analysis-runs/{run_id}/recheck")
        assert rechecked.status_code == 200, rechecked.text
        assert all(not row["stale"] for row in client.get(
            f"/api/v2/analysis-runs/{run_id}/decisions",
        ).json())
        corrected = client.put(
            f"/api/v2/pages/{page['id']}/text", json={"text": "Manually verified page text"},
        )
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["parse_mode"] == "manual"
        current_spans = client.get(f"/api/v2/pages/{page['id']}/source-spans").json()
        assert len(current_spans) == 1
        assert current_spans[0]["quote"] == "Manually verified page text"
        assert client.post(f"/api/v2/analysis-runs/{run_id}/recheck").status_code == 409
        report = client.get(f"/api/v2/analysis-runs/{run_id}/report").json()["markdown"]
        assert "资料已更新" in report
        assert "Checked source" in report


def test_manual_fill_positions_survive_rebuild_and_export(empty_table_pdf, monkeypatch):
    async def reject_network(*_args, **_kwargs):
        raise AssertionError("Offline workflow attempted a model request")

    monkeypatch.setattr("httpx.AsyncClient.post", reject_network)
    with TestClient(app) as client:
        _project, documents, run = prepare(client, empty_table_pdf, ["tender", "template"])
        run_id = run["id"]
        page = client.get(f"/api/v2/documents/{documents[1]['id']}/pages").json()[0]
        plan = client.post(f"/api/v2/analysis-runs/{run_id}/fill-plan", json={}).json()
        added = client.post(
            f"/api/v2/fill-plans/{plan['id']}/targets",
            json={
                "page_id": page["id"], "label": "Contact person",
                "kind": "text_box", "bbox": [50, 230, 250, 270],
            },
        )
        assert added.status_code == 201, added.text
        target = next(row for row in added.json()["targets"] if row["label"] == "Contact person")
        suggestion = target["suggestions"][0]
        saved = client.patch(
            f"/api/v2/fill-suggestions/{suggestion['id']}",
            json={"value": "张先生，已核实", "status": "edited"},
        )
        assert saved.status_code == 200, saved.text
        edited = client.patch(
            f"/api/v2/fill-targets/{target['id']}",
            json={"bbox": [50, 230, 260, 275]},
        )
        assert edited.status_code == 200, edited.text
        assert any(
            item["label"] == "Contact person" and item["coordinate_quality"] == "manual"
            for asset in edited.json()["assets"] for item in asset["annotations"]
        )
        bundle = client.get(f"/api/v2/analysis-runs/{run_id}/export")
        assert bundle.status_code == 200, bundle.text
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            names = archive.namelist()
            assert "投标准备检查报告.md" in names
            assert "填写内容清单.csv" in names
            assert any(name.startswith("标注图/") for name in names)
            assert "张先生，已核实" in archive.read("填写内容清单.csv").decode("utf-8-sig")
        rebuilt = client.post(f"/api/v2/analysis-runs/{run_id}/fill-plan", json={}).json()
        target = next(row for row in rebuilt["targets"] if row["label"] == "Contact person")
        assert target["suggestions"][0]["value"] == "张先生，已核实"
        removed = client.delete(f"/api/v2/fill-targets/{target['id']}")
        assert removed.status_code == 200, removed.text
        again = client.post(f"/api/v2/analysis-runs/{run_id}/fill-plan", json={}).json()
        assert not any(row["label"] == "Contact person" for row in again["targets"])
        deleted = client.delete(f"/api/v2/documents/{documents[1]['id']}")
        assert deleted.status_code == 204, deleted.text
        checklist = client.get(f"/api/v2/analysis-runs/{run_id}/checklist").json()
        assert not any(item["title"].startswith("确认填写：") for item in checklist)


def test_parse_failure_is_visible_and_can_be_requeued(empty_table_pdf, monkeypatch):
    def broken_parser(*_args):
        raise RuntimeError("Fixture parser failure")

    monkeypatch.setattr("app.services.handlers.parse_document", broken_parser)
    with TestClient(app) as client:
        project = client.post("/api/v2/projects", json={"name": "Parse failure fixture"}).json()
        response = client.post(
            f"/api/v2/projects/{project['id']}/documents",
            data={"role": "tender"},
            files={"file": ("fixture.pdf", empty_table_pdf.read_bytes(), "application/pdf")},
        )
        document_id = response.json()["id"]
        asyncio.run(_run_worker_until(client, project["id"]))
        failed = client.get(f"/api/v2/documents/{document_id}").json()
        assert failed["parse_status"] == "failed"
        assert "Fixture parser failure" in failed["parse_error"]
        requeued = client.post(f"/api/v2/documents/{document_id}/reparse")
        assert requeued.status_code == 200, requeued.text
        assert requeued.json()["parse_status"] == "queued"
        queued = next(job for job in client.get(
            f"/api/v2/projects/{project['id']}/jobs",
        ).json() if job["status"] == "queued")
        client.post(f"/api/v2/jobs/{queued['id']}/cancel")
        assert client.get(f"/api/v2/documents/{document_id}").json()["parse_status"] == "canceled"
