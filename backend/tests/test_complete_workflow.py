"""Complete customer journey; model boundaries are stubbed and external HTTP blocked."""
import asyncio
import io
import json
import zipfile

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_end_to_end import _run_worker_until

from app.config import get_settings
from app.db import get_engine
from app.main import app
from app.models import EmbeddingRecord, FillPlan, FillSuggestion, ModelCall
from app.services import model_gateway
from app.storage import sha256_text


def stub_models(monkeypatch):
    calls = []

    async def blocked(*_args, **_kwargs):
        raise AssertionError("External HTTP is forbidden")

    async def complete(_session, *, user, purpose, **_kwargs):
        calls.append(purpose)
        data = json.loads(user[user.index("{"):])
        if purpose == "extract_enterprise_material":
            block = next(b for b in data["blocks"] if "ISO9001" in b["text"])
            result = {"materials": [{
                "kind": "qualification", "title": "ISO9001", "entity_key": "fixture",
                "holder": "Acme", "facts": [{
                    "key": key, field: value, "block_id": block["block_id"], "quote": block["text"],
                } for key, field, value in [
                    ("certificate_name", "value_text", "ISO9001"),
                    ("valid_until", "value_date", "2028-12-31"),
                ]],
            }]}
        elif purpose == "extract_requirements":
            block = next(b for b in data["blocks"] if "ISO9001" in b["text"])
            result = {"requirements": [{
                "title": "ISO9001", "statement": "ISO9001 certificate required",
                "category": "qualification", "block_id": block["block_id"], "quote": "ISO9001",
                "condition_json": {"type": "certificate", "certificate": "ISO9001"},
            }]}
        elif purpose == "compare_requirement":
            evidence = data["candidates"][0]
            result = {"verdict": "supports", "reason": "Offline", "coverage_complete": True,
                      "conditions": [{
                          "condition_id": c["condition_id"], "label": "ISO9001",
                          "status": "supports", "reason": "Offline",
                          "evidence_ids": [evidence["evidence_id"]],
                          "source_span_ids": [evidence["source_span_ids"][0]],
                      } for c in data["condition_catalog"]]}
        elif purpose == "draft_fill_values":
            result = {"drafts": [{"target_id": t["target_id"], "value": None,
                                  "rationale": "Offline fixture: manual input required"}
                                 for t in data["targets"]]}
        else:
            raise AssertionError(f"Unstubbed model purpose: {purpose}")
        return json.dumps(result)

    async def embeddings(session, texts, *, config_id=None, **_kwargs):
        config = (await model_gateway.get_active_model(session, config_id)).config
        signature = model_gateway.embedding_signature(config)
        records = []
        created = False
        for text in texts:
            key = sha256_text(f"{signature}|{sha256_text(text)}")
            record = await session.get(EmbeddingRecord, key)
            if record is None:
                record = EmbeddingRecord(id=key, model_signature=signature,
                                         content_hash=sha256_text(text), vector=[1.0, 0.0])
                session.add(record)
                await session.flush()
                created = True
            records.append(record)
        if created:
            # The real gateway commits new vectors with its call record before returning.
            await session.commit()
        return signature, records

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    monkeypatch.setattr(model_gateway, "complete_text", complete)
    monkeypatch.setattr("app.services.library.embed_texts", embeddings)
    monkeypatch.setattr("app.services.retrieval.embed_texts", embeddings)
    # This isolated test enables scheduling only after replacing/blocking all external boundaries.
    monkeypatch.setenv("TENDER_LIVE_MODEL_CALLS", "true")
    get_settings.cache_clear()
    return calls


def checked(response):
    assert response.is_success, response.text
    return response.json()


def test_complete_upload_review_change_and_export(empty_table_pdf, monkeypatch):
    calls = stub_models(monkeypatch)
    with TestClient(app) as client:
        checked(client.post("/api/v2/model-configs", json={
            "name": "Offline stub", "base_url": "https://offline.invalid/v1",
            "api_key": "fixture", "text_model": "stub", "embedding_model": "stub",
        }))
        org = checked(client.post("/api/v2/organizations", json={"name": "Acme"}))
        proof_url = f"/api/v2/organizations/{org['id']}/documents"
        checked(client.post(proof_url, files={"file": (
            "certificate.csv", b"certificate,holder,valid_until\nISO9001,Acme,2028-12-31\n",
            "text/csv",
        )}))
        project = checked(client.post("/api/v2/projects", json={
            "name": "Complete offline journey", "organization_id": org["id"], "bidder_name": "Acme",
            "bid_deadline": "2027-01-05T09:00:00+08:00",
        }))
        project_url = f"/api/v2/projects/{project['id']}"
        values = [checked(client.post(f"{project_url}/response-values", json={
            "key": label, "label": label, "value_text": value, "review_status": "verified",
        })) for label, value in [("Equipment", "Cabinet A"), ("Specification", "IP65"),
                                 ("Quantity", "2")]]
        for role, name, content in [
            ("tender", "tender.csv", b"requirement\nISO9001 certificate required\n"),
            ("template", "template.pdf", empty_table_pdf.read_bytes()),
        ]:
            checked(client.post(f"{project_url}/documents", data={"role": role},
                                files={"file": (name, content, "application/octet-stream")}))
        asyncio.run(_run_worker_until(client, project["id"], expected_documents=2,
                                      expected_runs=True))
        assert checked(client.get(proof_url))[0]["evidence_count"] == 1
        assert len(checked(client.get(f"{project_url}/evidence"))) == 1
        runs = checked(client.get(f"{project_url}/analysis-runs"))
        assert len(runs) == 1
        run_url = f"/api/v2/analysis-runs/{runs[0]['id']}"
        assert checked(client.get(f"{run_url}/decisions"))[0]["status"] == "met"
        plan = checked(client.get(f"{run_url}/fill-plan"))
        assert plan["assets"] and len(plan["targets"]) == 3
        for target in plan["targets"]:
            suggestion = target["suggestions"][0]
            assert suggestion["value"] and suggestion["source_refs"]
            checked(client.patch(f"/api/v2/fill-suggestions/{suggestion['id']}",
                                 json={"status": "accepted"}))
        signed = checked(client.post(f"/api/v2/fill-plans/{plan['id']}/targets", json={
            "page_id": plan["targets"][0]["page_id"], "label": "Signature",
            "kind": "signature", "bbox": [50, 310, 250, 335],
        }))
        signature = next(t for t in signed["targets"] if t["kind"] == "signature")
        checked(client.patch(f"/api/v2/fill-suggestions/{signature['suggestions'][0]['id']}",
                             json={"status": "accepted", "value": ""}))
        assert "已确认线下签章" in checked(client.get(f"{run_url}/report"))["markdown"]
        assert checked(client.get(run_url))["status"] == "completed"
        checked(client.patch(project_url, json={"auto_analyze": False}))
        checked(client.patch(f"/api/v2/response-values/{values[0]['id']}",
                             json={"value_text": "Cabinet B"}))
        assert checked(client.get(run_url))["status"] == "stale"
        changed = checked(client.get(f"{run_url}/fill-plan"))
        assert all(t["suggestions"][0]["status"] == "proposed" for t in changed["targets"])
        assert checked(client.post(f"{run_url}/recheck"))["status"] == "needs_review"
        assert any(not i["completed"] for i in checked(client.get(f"{run_url}/checklist")))
        checked(client.post(f"/api/v2/fill-plans/{plan['id']}/draft"))
        asyncio.run(_run_worker_until(client, project["id"]))
        refreshed = checked(client.get(f"{run_url}/fill-plan"))
        assert any(t["suggestions"][0]["value"] == "Cabinet B" for t in refreshed["targets"])
        for target in refreshed["targets"]:
            checked(client.patch(f"/api/v2/fill-suggestions/{target['suggestions'][0]['id']}",
                                 json={"status": "accepted"}))
        assert checked(client.get(run_url))["status"] == "completed"
        exported = client.get(f"{run_url}/export")
        assert exported.status_code == 200, exported.text
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            text = archive.read("填写内容清单.csv").decode("utf-8-sig")
            assert "Cabinet B" in text and "Cabinet A" not in text
            assert any(name.endswith(".png") for name in archive.namelist())
            assert "已确认线下签章" in text
            image_name = next(name for name in archive.namelist() if name.endswith(".png"))
            previous_image = archive.read(image_name)
        # A draft interrupted after committing values must not export its previous page image.
        current = checked(client.get(f"{run_url}/fill-plan"))
        equipment = next(t for t in current["targets"] if t["label"] == "Equipment")

        async def interrupted_draft():
            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                await session.execute(update(FillSuggestion).where(
                    FillSuggestion.id == equipment["suggestions"][0]["id"],
                ).values(value="Saved partial draft", status="proposed"))
                await session.execute(update(FillPlan).where(FillPlan.id == plan["id"])
                                      .values(status="failed"))
                await session.commit()
                assert (await session.execute(select(func.count(ModelCall.id)))).scalar_one() == 0

        asyncio.run(interrupted_draft())
        partial = client.get(f"{run_url}/export")
        assert partial.status_code == 200, partial.text
        with zipfile.ZipFile(io.BytesIO(partial.content)) as archive:
            assert archive.read(image_name) != previous_image
            assert "Saved partial draft" in archive.read("填写内容清单.csv").decode("utf-8-sig")
            assert "填写起草未完成" in archive.read("投标准备检查报告.md").decode()
        assert {"extract_enterprise_material", "extract_requirements", "compare_requirement"} <= (
            set(calls)
        )
