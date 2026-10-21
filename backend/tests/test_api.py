from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_project_contract():
    with TestClient(app) as client:
        assert client.get("/api/v2/health").json()["status"] == "ok"
        created = client.post(
            "/api/v2/projects",
            json={"name": "测试项目", "tender_no": "T-001"},
        )
        assert created.status_code == 201
        project = created.json()
        assert project["name"] == "测试项目"
        listed = client.get("/api/v2/projects").json()
        assert any(item["id"] == project["id"] for item in listed)


def test_upload_sample_creates_parse_job():
    with TestClient(app) as client:
        project = client.post("/api/v2/projects", json={"name": "上传测试"}).json()
        sample = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"
        with sample.open("rb") as stream:
            response = client.post(
                f"/api/v2/projects/{project['id']}/documents",
                data={"role": "tender"},
                files={"file": (sample.name, stream, "application/pdf")},
            )
        assert response.status_code == 201, response.text
        document = response.json()
        assert document["filename"] == sample.name
        jobs = client.get(f"/api/v2/projects/{project['id']}/jobs").json()
        assert len(jobs) == 1
        assert jobs[0]["kind"] == "parse_document"
        assert jobs[0]["status"] == "queued"


def test_worker_processes_uploaded_document():
    import asyncio

    from app.services.jobs import worker_loop

    with TestClient(app) as client:
        project = client.post("/api/v2/projects", json={"name": "解析测试"}).json()
        sample = Path(__file__).parents[2] / "samples" / "控制柜配电柜变频柜采购招标公告_样本.pdf"
        with sample.open("rb") as stream:
            response = client.post(
                f"/api/v2/projects/{project['id']}/documents",
                data={"role": "tender"},
                files={"file": (sample.name, stream, "application/pdf")},
            )
        document = response.json()

        async def run_worker():
            stop = asyncio.Event()
            task = asyncio.create_task(worker_loop(stop, 0.05, 30))
            await asyncio.sleep(2)
            stop.set()
            await task

        asyncio.run(run_worker())
        parsed = client.get(f"/api/v2/documents/{document['id']}").json()
        assert parsed["page_count"] > 0
        pages = client.get(f"/api/v2/documents/{document['id']}/pages").json()
        assert len(pages) == parsed["page_count"]
