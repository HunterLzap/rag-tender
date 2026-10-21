import asyncio

from fastapi.testclient import TestClient
from test_end_to_end import _run_worker_until

from app.main import app


def test_project_document_evidence_and_response_crud(empty_table_pdf):
    with TestClient(app) as client:
        project = client.post("/api/v2/projects", json={"name": "CRUD fixture"}).json()
        project_id = project["id"]
        patched = client.patch(
            f"/api/v2/projects/{project_id}", json={"name": "Edited project"}
        )
        assert patched.json()["name"] == "Edited project"
        with empty_table_pdf.open("rb") as source:
            document = client.post(
                f"/api/v2/projects/{project_id}/documents",
                data={"role": "evidence"},
                files={"file": ("proof.pdf", source, "application/pdf")},
            ).json()
        document_id = document["id"]
        asyncio.run(_run_worker_until(client, project_id, expected_documents=1))
        renamed = client.patch(
            f"/api/v2/documents/{document_id}", json={"filename": "renamed.pdf"}
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["filename"] == "renamed.pdf"
        download = client.get(f"/api/v2/documents/{document_id}/file")
        assert download.content == empty_table_pdf.read_bytes()
        page = client.get(f"/api/v2/documents/{document_id}/pages").json()[0]
        span = client.get(f"/api/v2/pages/{page['id']}/source-spans").json()[0]
        created = client.post(
            f"/api/v2/projects/{project_id}/evidence",
            json={
                "kind": "qualification",
                "title": "Evidence fixture",
                "source_span_id": span["id"],
                "payload": {"certificate_name": "Original certificate"},
            },
        )
        assert created.status_code == 201, created.text
        evidence_id = created.json()["id"]
        assert created.json()["source_span"]["quote"]
        edited = client.patch(
            f"/api/v2/evidence/{evidence_id}",
            json={"payload": {"certificate_name": "Updated certificate"}},
        )
        assert edited.status_code == 200, edited.text
        assert [fact["value_text"] for fact in edited.json()["facts"]] == ["Updated certificate"]
        assert client.delete(f"/api/v2/documents/{document_id}").status_code == 409
        assert client.delete(f"/api/v2/evidence/{evidence_id}").status_code == 204
        assert client.delete(f"/api/v2/documents/{document_id}").status_code == 204
        value = client.post(
            f"/api/v2/projects/{project_id}/response-values",
            json={"key": "field_fixture", "label": "Equipment", "value_text": "Control cabinet"},
        ).json()
        updated = client.patch(
            f"/api/v2/response-values/{value['id']}", json={"value_text": "Updated cabinet"}
        )
        assert updated.json()["value_text"] == "Updated cabinet"
        assert client.delete(f"/api/v2/response-values/{value['id']}").status_code == 204
        assert client.delete(f"/api/v2/projects/{project_id}").status_code == 204


def test_model_config_edit_preserves_encrypted_key_without_model_calls():
    with TestClient(app) as client:
        created = client.post(
            "/api/v2/model-configs",
            json={
                "name": "Offline fixture",
                "base_url": "https://example.invalid/v1",
                "text_model": "fixture-model",
                "api_key": "offline-placeholder-key",
                "is_active": False,
            },
        )
        assert created.status_code == 201
        config_id = created.json()["id"]
        updated = client.patch(
            f"/api/v2/model-configs/{config_id}",
            json={"name": "Renamed fixture", "text_model": "updated-model"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["text_model"] == "updated-model"
        assert "offline-placeholder-key" not in updated.text
        assert client.delete(f"/api/v2/model-configs/{config_id}").status_code == 204
