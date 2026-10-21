import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import model_gateway
from app.services.extraction import _block_batches
from app.services.jobs import worker_loop

SAMPLE = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"


def test_mock_model_pipeline_and_fill_review(monkeypatch, empty_table_pdf):
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
                None,
            )
            if candidate is None:
                return extraction.ExtractedRequirements()
            block_id = candidate["block_id"]
            return extraction.ExtractedRequirements(
                requirements=[
                    extraction.ExtractedRequirement(
                        title="Equipment 响应",
                        statement="须填写设备名称",
                        category="submission",
                        evaluation_stage="compliance",
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
        project = client.post("/api/v2/projects", json={"name": "离线验收（模拟模型）"}).json()
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
                "label": "Equipment",
                "value_text": "智能控制柜",
                "review_status": "verified",
            },
        )
        assert response_value.status_code == 201, response_value.text

        for role, source in (("tender", SAMPLE), ("template", empty_table_pdf)):
            with source.open("rb") as stream:
                response = client.post(
                    f"/api/v2/projects/{project['id']}/documents",
                    data={"role": role},
                    files={"file": (source.name, stream, "application/pdf")},
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
        refreshed = client.get(f"/api/v2/analysis-runs/{run_id}/fill-plan").json()
        assert refreshed["id"] == plan_body["id"]
        annotation = next(
            annotation
            for asset in refreshed["assets"]
            for annotation in asset["annotations"]
            if annotation["label"] == "Equipment"
        )
        assert annotation["value"] == "智能控制柜（已复核）"
        assert annotation["coordinate_quality"] == "exact"
        assert annotation["reference_only"] is False
        assert len(refreshed["targets"]) == 3
        assert all(target["suggestions"] for target in refreshed["targets"])
        image = client.get(f"/api/v2/annotation-assets/{plan_body['assets'][0]['id']}/image")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        rebuilt = client.post(f"/api/v2/analysis-runs/{run_id}/fill-plan", json={})
        assert rebuilt.status_code == 201, rebuilt.text
        assert rebuilt.json()["id"] == plan_body["id"]
        assert len(rebuilt.json()["targets"]) == 3
        assert any(
            item["value"] == "智能控制柜（已复核）" and item["status"] == "edited"
            for target in rebuilt.json()["targets"]
            for item in target["suggestions"]
        )
        report = client.get(f"/api/v2/analysis-runs/{run_id}/report").json()
        assert "交付检查清单" in report["markdown"]
        assert "智能控制柜（已复核）" in report["markdown"]
        assert client.delete(f"/api/v2/analysis-runs/{run_id}").status_code == 204
        assert client.get(f"/api/v2/analysis-runs/{run_id}").status_code == 404
        deleted = client.delete(f"/api/v2/projects/{project['id']}")
        assert deleted.status_code == 204, deleted.text
        assert client.get(f"/api/v2/projects/{project['id']}").status_code == 404


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
            attempts=1,
            max_attempts=1,
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


def test_blocks_are_split_into_bounded_batches():
    class Block:
        def __init__(self, index):
            self.text = "x" * 800
            self.index = index

    batches = _block_batches([Block(index) for index in range(20)])
    assert len(batches) == 3
    assert all(1 < len(batch) <= 8 for batch in batches)
    assert all(sum(len(block.text) for block in batch) <= 6000 for batch in batches)
    from types import SimpleNamespace

    large = SimpleNamespace(id="original", kind="table", text="x" * 14000)
    bounded = _block_batches([large])
    assert all(sum(len(block.text) for block in batch) <= 6000 for batch in bounded)
    assert all(block.id == "original" for batch in bounded for block in batch)


def test_default_data_dir_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    from app.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TENDER_DATA_DIR")
    settings = Settings()
    assert settings.resolved_data_dir == Path(__file__).parents[2] / "data"


@pytest.mark.asyncio
async def test_truncated_model_output_is_recorded_as_failure(session, monkeypatch):
    from app.models import ModelCall, ModelConfig

    session.add(
        ModelConfig(
            name="test",
            base_url="https://example.invalid/v1",
            api_key_encrypted="unused",
            text_model="test-model",
            is_active=True,
        )
    )
    await session.commit()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {"content": '{"x":'},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8192},
            }

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(model_gateway.httpx, "AsyncClient", Client)
    monkeypatch.setattr(model_gateway, "decrypt_secret", lambda _value: "test-key")
    monkeypatch.setenv("TENDER_LIVE_MODEL_CALLS", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(model_gateway.ModelOutputTruncated):
        await model_gateway.complete_text(
            session,
            system="system",
            user="user",
            purpose="test",
            max_tokens=8192,
        )

    call = (await session.execute(__import__("sqlalchemy").select(ModelCall))).scalar_one()
    assert call.success is False
    assert call.output_tokens == 8192
    assert "长度上限" in (call.error or "")


async def test_live_model_calls_are_disabled_by_default(session):
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(model_gateway.LiveModelCallsDisabled):
        await model_gateway.complete_text(
            session,
            system="system",
            user="user",
            purpose="test",
        )
    from app.services.vision import transcribe_scanned_page

    with pytest.raises(model_gateway.LiveModelCallsDisabled):
        await transcribe_scanned_page(session, Path("unused.png"))
    success, _, _ = await model_gateway.test_model(
        base_url="https://example.invalid/v1", api_key="unused", model="unused"
    )
    assert success is False
