import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import get_engine
from app.main import app
from app.models import AnalysisRun, AnalysisStatus, Document, Job, ModelCall
from app.services.jobs import _process_one, claim_job
from app.services.library import index_document
from app.services.retrieval import recall_evidence


def test_shared_materials_sources_corrections_and_project_deletion():
    with TestClient(app) as client:
        first = client.post("/api/v2/organizations", json={"name": "Acme"}).json()
        other = client.post("/api/v2/organizations", json={"name": "Other company"}).json()
        projects = [
            client.post(
                "/api/v2/projects",
                json={
                    "name": f"Tender {index}",
                    "organization_id": organization["id"],
                },
            ).json()
            for index, organization in enumerate((first, first, other))
        ]
        url = f"/api/v2/organizations/{first['id']}/documents"
        files = {"file": ("certificate.csv", b"certificate,holder\nISO9001,Acme\n", "text/csv")}
        upload = client.post(url, files=files)
        assert upload.status_code == 201, upload.text
        document = upload.json()
        assert document["project_id"] is None
        assert client.post(url, files=files).json()["id"] == document["id"]
        asyncio.run(_parse_one())
        parsed = client.get(url).json()[0]
        assert parsed["current_revision_id"]
        assert parsed["ai_status"] == "waiting_api"
        for project in projects[:2]:
            assert client.get(f"/api/v2/projects/{project['id']}/documents").json() == []
            shared = client.get(f"/api/v2/projects/{project['id']}/library-documents").json()
            assert [item["id"] for item in shared] == [document["id"]]
        assert client.get(f"/api/v2/projects/{projects[2]['id']}/library-documents").json() == []
        page = client.get(f"/api/v2/documents/{document['id']}/pages").json()[0]
        span = client.get(f"/api/v2/pages/{page['id']}/source-spans").json()[0]
        created = client.post(
            f"/api/v2/projects/{projects[0]['id']}/evidence",
            json={
                "kind": "qualification",
                "title": "ISO9001 certificate",
                "holder": "Acme",
                "source_span_id": span["id"],
                "payload": {"certificate_name": "ISO9001"},
            },
        )
        assert created.status_code == 201, created.text
        evidence = created.json()
        assert evidence["organization_id"] == first["id"]
        assert evidence["facts"][0]["source_span"]["id"] == span["id"]
        verified = client.patch(
            f"/api/v2/evidence/{evidence['id']}",
            json={
                "review_status": "verified",
            },
        ).json()
        assert verified["facts"][0]["id"] == evidence["facts"][0]["id"]
        assert verified["facts"][0]["source_span"]["id"] == span["id"]
        asyncio.run(_index_and_recall(document["id"], projects, evidence["id"]))
        changed = client.patch(
            f"/api/v2/evidence-facts/{evidence['facts'][0]['id']}",
            json={
                "value_text": "ISO9001 (verified)",
                "review_status": "verified",
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["source_span"]["id"] == span["id"]
        for project in projects[:2]:
            rows = client.get(f"/api/v2/projects/{project['id']}/evidence").json()
            assert rows[0]["facts"][0]["value_text"] == "ISO9001 (verified)"
            assert (
                client.get(f"/api/v2/projects/{project['id']}/analysis-runs").json()[0]["status"]
                == "stale"
            )
        assert client.get(f"/api/v2/projects/{projects[2]['id']}/evidence").json() == []
        assert client.delete(f"/api/v2/projects/{projects[0]['id']}").status_code == 204
        assert client.get(url).json()[0]["id"] == document["id"]
        assert client.delete(f"/api/v2/documents/{document['id']}").status_code == 204
        assert client.get(f"/api/v2/projects/{projects[1]['id']}/evidence").json() == []
        asyncio.run(_assert_no_model_work())


async def _parse_one():
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        job = await claim_job(session, "offline-library-test", 30)
        assert job.kind == "parse_document"
        await _process_one(session, job)
        await session.refresh(job)
        assert job.status == "completed", job.error


async def _index_and_recall(document_id, projects, evidence_id):
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        document = await session.get(Document, document_id)
        assert await index_document(session, document, with_embeddings=False) > 0
        for index, project in enumerate(projects):
            candidates = await recall_evidence(
                session,
                project_id=project["id"],
                kind="qualification",
                query="ISO9001",
            )
            assert [item.evidence.id for item in candidates] == ([evidence_id] if index < 2 else [])
            if index < 2:
                session.add(
                    AnalysisRun(
                        project_id=project["id"],
                        status=AnalysisStatus.COMPLETED,
                    )
                )
        await session.commit()


async def _assert_no_model_work():
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        assert (await session.execute(select(func.count(ModelCall.id)))).scalar_one() == 0
        assert (
            await session.execute(
                select(Job).where(
                    Job.kind.in_(["process_document", "analyze_project", "draft_fill_plan"]),
                )
            )
        ).scalars().all() == []
