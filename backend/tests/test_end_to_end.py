import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.jobs import worker_loop

SAMPLE = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"


def test_mock_model_pipeline_and_fill_review(monkeypatch):
    from app.services import extraction
    from app.services.model_eval import SemanticAssessment

    async def fake_structured_text(
        _session,
        *,
        system,
        user,
        output_model,
        **_kwargs,
    ):
        if output_model is extraction.ExtractedRequirements:
            import json
            import re

            match = re.search(r"\{.*\}", user, re.S)
            if not match:
                return extraction.ExtractedRequirements()
            payload = json.loads(match.group(0))
            candidate = next(
                (block for block in payload["blocks"] if "设备名称" in block["text"]),
                payload["blocks"][0],
            )
            block_id = candidate["block_id"]
            return extraction.ExtractedRequirements(
                requirements=[
                    extraction.ExtractedRequirement(
                        title="设备名称响应",
                        statement="须填写设备名称",
                        category="submission",
                        evaluation_stage="符合性审查",
                        handling_mode="fill",
                        block_id=block_id,
                        quote="设备名称",
                    )
                ]
            )
        if output_model is SemanticAssessment:
            return SemanticAssessment(verdict="insufficient", reason="测试")
        raise AssertionError(output_model)

    monkeypatch.setattr(extraction, "structured_text", fake_structured_text)
    with TestClient(app) as client:
        project = client.post("/api/v2/projects", json={"name": "端到端测试"}).json()
        bid = client.post(
            f"/api/v2/projects/{project['id']}/bids",
            json={
                "bidder_name": "测试投标人",
                "bid_deadline": "2027-01-05T09:00:00+08:00",
                "as_of_date": "2027-01-05",
            },
        )
        assert bid.status_code == 201, bid.text
        response_value = client.post(
            f"/api/v2/projects/{project['id']}/response-values",
            json={
                "key": "equipment_name",
                "label": "设备名称",
                "value_text": "智能控制柜",
                "review_status": "verified",
            },
        )
        assert response_value.status_code == 201, response_value.text

        for role in ("tender", "template"):
            with SAMPLE.open("rb") as stream:
                response = client.post(
                    f"/api/v2/projects/{project['id']}/documents",
                    data={"role": role},
                    files={"file": (SAMPLE.name, stream, "application/pdf")},
                )
            assert response.status_code == 201, response.text

        asyncio.run(_run_worker_until(client, project["id"], expected_documents=2))

        run = client.post(f"/api/v2/projects/{project['id']}/analysis-runs", json={})
        assert run.status_code == 201, run.text
        run_id = run.json()["id"]
        asyncio.run(_run_worker_until(client, project["id"], expected_runs=True))
        details = client.get(f"/api/v2/analysis-runs/{run_id}")
        assert details.status_code == 200, details.text
        assert details.json()["requirement_count"] > 0
        decisions = client.get(f"/api/v2/analysis-runs/{run_id}/decisions").json()
        assert decisions
        review = client.post(
            f"/api/v2/decisions/{decisions[0]['id']}/reviews",
            json={"new_status": "met", "reason": "人工核对通过"},
        )
        assert review.status_code == 201, review.text

        plan = client.post(f"/api/v2/analysis-runs/{run_id}/fill-plan", json={})
        assert plan.status_code == 201, plan.text
        plan_body = plan.json()
        assert plan_body["targets"]
        suggestion = next(
            item
            for target in plan_body["targets"]
            for item in target["suggestions"]
            if item["value"] == "智能控制柜"
        )
        edited = client.patch(
            f"/api/v2/fill-suggestions/{suggestion['id']}",
            json={"value": "智能控制柜（已复核）", "status": "edited"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["status"] == "edited"
        assert edited.json()["reviewed_at"]
        image = client.get(f"/api/v2/annotation-assets/{plan_body['assets'][0]['id']}/image")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"


async def _run_worker_until(
    client: TestClient,
    project_id: str,
    *,
    expected_documents: int = 0,
    expected_runs: bool = False,
) -> None:
    for _ in range(120):
        stop = asyncio.Event()
        task = asyncio.create_task(worker_loop(stop, 0.02, 30))
        await asyncio.sleep(0.25)
        stop.set()
        await task
        jobs = client.get(f"/api/v2/projects/{project_id}/jobs").json()
        if any(job["status"] in {"queued", "running"} for job in jobs):
            continue
        if expected_documents:
            documents = client.get(f"/api/v2/projects/{project_id}/documents").json()
            if sum(bool(doc["current_revision_id"]) for doc in documents) < expected_documents:
                continue
        if expected_runs:
            runs = client.get(f"/api/v2/projects/{project_id}/analysis-runs").json()
            if not runs or runs[0]["status"] in {"draft", "running"}:
                continue
        return
    raise AssertionError("worker did not finish")


def test_worker_failure_retries_and_marks_analysis_failed(session):
    from app.models import AnalysisRun, AnalysisStatus, Job, JobStatus
    from app.services.jobs import _handlers, _process_one

    async def scenario():
        run = AnalysisRun(project_id="missing", status=AnalysisStatus.RUNNING)
        session.add(run)
        await session.flush()
        job = Job(
            kind="analyze_project",
            payload={"run_id": run.id},
            status=JobStatus.RUNNING,
            attempts=3,
            max_attempts=3,
        )
        session.add(job)
        await session.commit()

        original = _handlers["analyze_project"]
        _handlers["analyze_project"] = _raise_expected
        try:
            await _process_one(session, job)
        finally:
            _handlers["analyze_project"] = original
        await session.refresh(job)
        await session.refresh(run)
        assert job.status == JobStatus.FAILED
        assert run.status == AnalysisStatus.FAILED
        assert "expected failure" in (run.error or "")

    import asyncio

    asyncio.run(scenario())


async def _raise_expected(_session, _job):
    raise RuntimeError("expected failure")
