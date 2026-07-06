"""规则库 API 测试。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from app import database

_TEMP_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
database.DB_PATH = str(Path(_TEMP_DIR.name) / "rules_api.db")

from app.database import init_db
from app.main import app


def _seed_match_correction_for_suggestion() -> None:
    import sqlite3

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM custom_rules")
        conn.execute("DELETE FROM rule_drafts")
        conn.execute("DELETE FROM rule_suggestion_reviews")
        conn.execute("DELETE FROM match_corrections WHERE id = 1")
        conn.execute("DELETE FROM tender_requirements WHERE id = 10")
        conn.execute("DELETE FROM tenders WHERE id = 1")
        conn.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (1, 'sample.pdf', 'sample.pdf', '测试标书', 'completed', '2026-07-02')"""
        )
        conn.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (10, 1, 'qualification', 'capability', '依法缴纳税收和社保',
                       '投标人须依法缴纳税收和社会保障资金。', 1, '原文', '2026-07-02')"""
        )
        conn.execute(
            """INSERT INTO match_corrections
               (id, match_id, tender_id, requirement_id, qualification_id, previous_status,
                confirmed_status, correction_reason, evidence_snapshot, created_at)
               VALUES (1, 99, 1, 10, NULL, 'matched', 'unmatched',
                       '只有纳税证明，没有社保证明，不能判定符合',
                       '[{"check_key":"social_security","status":"unknown"}]',
                       '2026-07-02 10:00:00')"""
        )
        conn.commit()


def test_rule_catalog_api_returns_builtin_rules() -> None:
    asyncio.run(init_db())
    client = TestClient(app)

    resp = client.get("/api/v1/rules")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert any(item["id"] == "submission.red_flag.deposit" for item in body["data"])
    assert any(item["rule_type"] == "red_flag" for item in body["data"])


def test_rule_templates_api_returns_common_tender_analysis_templates() -> None:
    asyncio.run(init_db())
    client = TestClient(app)

    resp = client.get("/api/v1/rules/templates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    templates = body["data"]
    assert isinstance(templates, list)
    assert len(templates) >= 8
    assert any(item["id"] == "template.tax_social_security_evidence" for item in templates)
    assert any(item["category"] == "资格审查" for item in templates)
    assert any(item["category"] == "技术响应" for item in templates)
    tax_template = next(
        item for item in templates if item["id"] == "template.tax_social_security_evidence"
    )
    assert tax_template["rule_type"] == "required_evidence_rule"
    assert tax_template["risk_level"] == "high"
    assert "社保证明" in tax_template["evidence_requirements"]
    assert tax_template["positive_examples"]
    assert tax_template["negative_examples"]
    assert "参考模板" in tax_template["review_notes"]


def test_rule_template_can_create_pending_rule_draft() -> None:
    import sqlite3

    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM rule_drafts WHERE source_suggestion_id LIKE 'template:%'")
        conn.commit()
    client = TestClient(app)

    resp = client.post(
        "/api/v1/rules/templates/template.tax_social_security_evidence/draft",
        json={"reason": "本项目需要补充纳税和社保证据核验口径"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    draft = body["data"]
    assert draft["source_suggestion_id"].startswith("template:template.tax_social_security_evidence:")
    assert draft["name"] == "模板草案：依法纳税和社保证明核验"
    assert draft["rule_type"] == "required_evidence_rule"
    assert draft["draft_status"] == "pending_review"
    assert "证据要求：纳税证明、社保证明" in draft["draft_content"]
    assert "使用原因：本项目需要补充纳税和社保证据核验口径" in draft["draft_content"]


def test_rule_template_reuses_existing_pending_draft() -> None:
    import sqlite3

    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM rule_drafts WHERE source_suggestion_id LIKE 'template:%'")
        conn.commit()
    client = TestClient(app)

    first = client.post(
        "/api/v1/rules/templates/template.tax_social_security_evidence/draft",
        json={"reason": "第一次从模板生成草案"},
    ).json()["data"]
    second = client.post(
        "/api/v1/rules/templates/template.tax_social_security_evidence/draft",
        json={"reason": "第二次点击不应重复创建"},
    ).json()["data"]

    assert second["id"] == first["id"]
    drafts = client.get("/api/v1/rules/drafts?limit=50").json()["data"]
    template_drafts = [
        item
        for item in drafts
        if item["source_suggestion_id"].startswith("template:template.tax_social_security_evidence:")
    ]
    assert len(template_drafts) == 1


def test_rule_catalog_api_updates_enabled_state() -> None:
    asyncio.run(init_db())
    client = TestClient(app)

    resp = client.put("/api/v1/rules/submission.red_flag.deposit/enabled", json={"enabled": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == "submission.red_flag.deposit"
    assert body["data"]["enabled"] is False

    rules_resp = client.get("/api/v1/rules")
    rules = rules_resp.json()["data"]
    deposit = next(item for item in rules if item["id"] == "submission.red_flag.deposit")
    assert deposit["enabled"] is False


def test_rule_catalog_api_records_enabled_change_reason() -> None:
    asyncio.run(init_db())
    client = TestClient(app)

    resp = client.put(
        "/api/v1/rules/submission.red_flag.deadline/enabled",
        json={"enabled": False, "reason": "该项目截止时间要求已由人工清单单独跟踪"},
    )
    assert resp.status_code == 200

    changes_resp = client.get("/api/v1/rules/changes?limit=20")

    assert changes_resp.status_code == 200
    body = changes_resp.json()
    assert body["code"] == 0
    changes = body["data"]
    assert len(changes) >= 1
    latest = changes[0]
    assert latest["rule_id"] == "submission.red_flag.deadline"
    assert latest["previous_enabled"] is True
    assert latest["new_enabled"] is False
    assert latest["reason"] == "该项目截止时间要求已由人工清单单独跟踪"


def test_rule_suggestions_api_returns_correction_based_candidates() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)

    resp = client.get("/api/v1/rules/suggestions?limit=20")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    suggestions = body["data"]
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["source"] == "match_correction"
    assert suggestion["suggestion_type"] == "tighten_rule"
    assert suggestion["requirement_title"] == "依法缴纳税收和社保"
    assert "社保证明" in suggestion["reason"]
    assert suggestion["confidence"] >= 0.7
    assert suggestion["quality_status"] == "actionable"
    assert "原因包含明确证据缺口" in suggestion["quality_notes"]
    assert "社保证明" in suggestion["evidence_gaps"]
    assert suggestion["review_status"] == "pending"


def test_rule_suggestions_skip_low_quality_correction_reason() -> None:
    import sqlite3

    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM match_corrections WHERE id = 1")
        conn.execute(
            """INSERT INTO match_corrections
               (id, match_id, tender_id, requirement_id, qualification_id, previous_status,
                confirmed_status, correction_reason, evidence_snapshot, created_at)
               VALUES (2, 100, 1, 10, NULL, 'matched', 'unmatched',
                       '不对',
                       '[]',
                       '2026-07-02 11:00:00')"""
        )
        conn.commit()
    client = TestClient(app)

    resp = client.get("/api/v1/rules/suggestions?limit=20")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"] == []


def test_rule_suggestion_review_updates_status_and_reason() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)

    resp = client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "rejected", "review_reason": "暂不作为通用规则，先观察更多错例"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["suggestion_id"] == "correction-1"
    assert body["data"]["review_status"] == "rejected"
    assert body["data"]["review_reason"] == "暂不作为通用规则，先观察更多错例"

    suggestions = client.get("/api/v1/rules/suggestions?limit=20").json()["data"]
    suggestion = next(item for item in suggestions if item["id"] == "correction-1")
    assert suggestion["review_status"] == "rejected"
    assert suggestion["review_reason"] == "暂不作为通用规则，先观察更多错例"


def test_accepting_rule_suggestion_creates_rule_draft() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)

    resp = client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    assert resp.status_code == 200

    drafts_resp = client.get("/api/v1/rules/drafts?limit=20")

    assert drafts_resp.status_code == 200
    body = drafts_resp.json()
    assert body["code"] == 0
    drafts = body["data"]
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft["source_suggestion_id"] == "correction-1"
    assert draft["draft_status"] == "pending_review"
    assert draft["rule_type"] == "tighten_rule"
    assert "依法缴纳税收和社保" in draft["name"]
    assert "社保证明" in draft["draft_content"]


def test_pending_rule_draft_can_be_updated_before_publish() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]

    resp = client.put(
        f"/api/v1/rules/drafts/{draft['id']}",
        json={
            "name": "规则草案：纳税与社保证明组合复核",
            "rule_type": "tighten_rule",
            "draft_content": "命中纳税和社保组合要求时，必须同时核验纳税证明和社保证明；缺任一项不得自动符合。",
            "edit_reason": "发布前补充更明确的证据要求",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == draft["id"]
    assert body["data"]["name"] == "规则草案：纳税与社保证明组合复核"
    assert "必须同时核验纳税证明和社保证明" in body["data"]["draft_content"]
    assert body["data"]["review_reason"] == "发布前补充更明确的证据要求"

    drafts = client.get("/api/v1/rules/drafts?limit=20").json()["data"]
    updated = next(item for item in drafts if item["id"] == draft["id"])
    assert updated["name"] == "规则草案：纳税与社保证明组合复核"
    assert "缺任一项不得自动符合" in updated["draft_content"]


def test_published_rule_draft_cannot_be_updated() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )

    resp = client.put(
        f"/api/v1/rules/drafts/{draft['id']}",
        json={
            "name": "不应保存的草案名称",
            "rule_type": "tighten_rule",
            "draft_content": "已发布草案不允许直接编辑。",
            "edit_reason": "尝试修改已发布草案",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != 0

    drafts = client.get("/api/v1/rules/drafts?limit=20").json()["data"]
    unchanged = next(item for item in drafts if item["id"] == draft["id"])
    assert unchanged["name"] == draft["name"]
    assert unchanged["draft_status"] == "published"


def test_rule_draft_similar_api_returns_existing_custom_rule() -> None:
    import sqlite3

    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO rule_drafts
               (id, source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (99, 'manual-duplicate', '规则草案：社保和纳税资料复核', 'tighten_rule',
                       '遇到税收和社会保障资金要求时，需要同时检查纳税证明和社保证明，缺失任一资料不得自动符合。',
                       'pending_review', '2026-07-02 12:00:00', '2026-07-02 12:00:00')"""
        )
        conn.commit()

    resp = client.get("/api/v1/rules/drafts/99/similar")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    similar = body["data"]
    assert len(similar) >= 1
    top = similar[0]
    assert top["rule_id"] == f"custom.rule_draft.{draft['id']}"
    assert top["source"] == "已发布自定义规则"
    assert top["similarity"] >= 0.2
    assert "规则类型相同" in top["reasons"]
    assert any("关键词重合" in reason for reason in top["reasons"])


def test_rule_draft_can_reuse_existing_rule_without_publishing_duplicate() -> None:
    import sqlite3

    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )
    reused_rule_id = f"custom.rule_draft.{draft['id']}"

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO rule_drafts
               (id, source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (200, 'manual-reuse', '规则草案：社保和纳税资料复核', 'tighten_rule',
                       '遇到税收和社会保障资金要求时，需要同时检查纳税证明和社保证明，缺失任一资料不得自动符合。',
                       'pending_review', '2026-07-02 12:00:00', '2026-07-02 12:00:00')"""
        )
        conn.commit()

    before_rules = client.get("/api/v1/rules").json()["data"]
    before_custom_count = len([item for item in before_rules if item["id"].startswith("custom.")])

    resp = client.put(
        "/api/v1/rules/drafts/200/reuse",
        json={"target_rule_id": reused_rule_id, "reason": "与已发布社保纳税复核规则重复，复用已有规则"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["draft_id"] == 200
    assert body["data"]["target_rule_id"] == reused_rule_id
    assert body["data"]["relation_type"] == "duplicate_of"

    drafts = client.get("/api/v1/rules/drafts?limit=200").json()["data"]
    reused_draft = next(item for item in drafts if item["id"] == 200)
    assert reused_draft["draft_status"] == "rejected"
    assert "复用已有规则" in reused_draft["review_reason"]

    after_rules = client.get("/api/v1/rules").json()["data"]
    after_custom_count = len([item for item in after_rules if item["id"].startswith("custom.")])
    assert after_custom_count == before_custom_count


def test_publishing_similar_rule_records_difference_reason() -> None:
    import sqlite3

    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )
    similar_rule_id = f"custom.rule_draft.{draft['id']}"

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO rule_drafts
               (id, source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (300, 'manual-still-publish', '规则草案：社保和纳税资料复核', 'tighten_rule',
                       '遇到税收和社会保障资金要求时，需要同时检查纳税证明和社保证明，缺失任一资料不得自动符合。',
                       'pending_review', '2026-07-02 12:00:00', '2026-07-02 12:00:00')"""
        )
        conn.commit()

    resp = client.put(
        "/api/v1/rules/drafts/300/review",
        json={
            "draft_status": "published",
            "review_reason": "仍然发布",
            "similar_rule_ids": [similar_rule_id],
            "difference_reason": "已有规则用于企业纳税社保，本规则用于项目人员社保资料复核",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["draft_status"] == "published"

    with sqlite3.connect(database.DB_PATH) as conn:
        row = conn.execute(
            """SELECT source_rule_id, target_rule_id, relation_type, reason
               FROM rule_relations
               WHERE source_rule_id = 'custom.rule_draft.300'
                 AND target_rule_id = ?""",
            (similar_rule_id,),
        ).fetchone()

    assert row is not None
    assert row[2] == "similar_to"
    assert "项目人员社保" in row[3]


def test_rule_relations_api_returns_traceable_rule_links() -> None:
    import sqlite3

    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )
    target_rule_id = f"custom.rule_draft.{draft['id']}"

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM rule_relations WHERE source_rule_id = 'custom.rule_draft.1301'")
        conn.execute("DELETE FROM custom_rules WHERE id = 'custom.rule_draft.1301'")
        conn.execute("DELETE FROM rule_drafts WHERE id = 1301 OR source_suggestion_id = 'manual-relation-display'")
        conn.execute(
            """INSERT INTO rule_drafts
               (id, source_suggestion_id, name, rule_type, draft_content,
                draft_status, created_at, updated_at)
               VALUES (1301, 'manual-relation-display', '规则草案：项目人员社保资料复核', 'tighten_rule',
                       '项目人员资格材料中涉及社保要求时，需要单独核查人员社保证明。',
                       'pending_review', '2026-07-02 12:30:00', '2026-07-02 12:30:00')"""
        )
        conn.commit()

    client.put(
        "/api/v1/rules/drafts/1301/review",
        json={
            "draft_status": "published",
            "review_reason": "仍然发布",
            "similar_rule_ids": [target_rule_id],
            "difference_reason": "已有规则用于企业纳税社保，本规则用于项目人员社保资料复核",
        },
    )

    resp = client.get("/api/v1/rules/custom.rule_draft.1301/relations")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"][0]["relation_type"] == "similar_to"
    assert body["data"][0]["direction"] == "outgoing"
    assert body["data"][0]["related_rule_id"] == target_rule_id
    assert body["data"][0]["related_rule_name"]
    assert "项目人员社保" in body["data"][0]["reason"]


def test_custom_rule_can_be_merged_into_existing_rule() -> None:
    import sqlite3

    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM rule_relations WHERE source_rule_id IN ('custom.merge.source', 'custom.merge.target')")
        conn.execute("DELETE FROM rule_change_logs WHERE rule_id IN ('custom.merge.source', 'custom.merge.target')")
        conn.execute("DELETE FROM custom_rules WHERE id IN ('custom.merge.source', 'custom.merge.target')")
        conn.execute(
            """INSERT INTO custom_rules
               (id, source_draft_id, name, rule_type, description, enabled, created_at, updated_at)
               VALUES ('custom.merge.target', 9101, '主规则：企业社保纳税复核', 'tighten_rule',
                       '企业社保纳税材料需要同时核查。', 1, '2026-07-02 13:00:00', '2026-07-02 13:00:00')"""
        )
        conn.execute(
            """INSERT INTO custom_rules
               (id, source_draft_id, name, rule_type, description, enabled, created_at, updated_at)
               VALUES ('custom.merge.source', 9102, '重复规则：社保纳税资料复核', 'tighten_rule',
                       '社保纳税材料需要同时核查。', 1, '2026-07-02 13:10:00', '2026-07-02 13:10:00')"""
        )
        conn.commit()

    client = TestClient(app)
    resp = client.put(
        "/api/v1/rules/custom.merge.source/merge",
        json={
            "target_rule_id": "custom.merge.target",
            "reason": "两条规则判断对象和证据要求一致，归并到主规则维护",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["source_rule_id"] == "custom.merge.source"
    assert body["data"]["target_rule_id"] == "custom.merge.target"
    assert body["data"]["relation_type"] == "merged_into"

    rules = client.get("/api/v1/rules").json()["data"]
    source_rule = next(item for item in rules if item["id"] == "custom.merge.source")
    assert source_rule["enabled"] is False

    relations = client.get("/api/v1/rules/custom.merge.source/relations").json()["data"]
    merged_relation = next(item for item in relations if item["relation_type"] == "merged_into")
    assert merged_relation["related_rule_id"] == "custom.merge.target"
    assert "归并到主规则" in merged_relation["reason"]


def test_custom_rule_update_records_previous_version() -> None:
    import sqlite3

    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        try:
            conn.execute("DELETE FROM rule_versions WHERE rule_id = 'custom.version.demo'")
        except sqlite3.OperationalError:
            pass
        conn.execute("DELETE FROM custom_rules WHERE id = 'custom.version.demo'")
        conn.execute(
            """INSERT INTO custom_rules
               (id, source_draft_id, name, rule_type, description, enabled, created_at, updated_at)
               VALUES ('custom.version.demo', 9201, '社保纳税复核', 'tighten_rule',
                       '检查企业纳税证明和社保证明。', 1, '2026-07-02 14:00:00', '2026-07-02 14:00:00')"""
        )
        conn.commit()

    client = TestClient(app)
    resp = client.put(
        "/api/v1/rules/custom.version.demo",
        json={
            "name": "社保纳税资料复核",
            "rule_type": "required_evidence_rule",
            "description": "检查企业纳税证明、社保证明，缺一项不得自动符合。",
            "edit_reason": "补充证据缺失时不得自动符合的约束",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "社保纳税资料复核"
    assert body["data"]["rule_type"] == "required_evidence_rule"
    assert "缺一项不得自动符合" in body["data"]["description"]

    versions = client.get("/api/v1/rules/custom.version.demo/versions").json()["data"]
    assert len(versions) == 1
    assert versions[0]["version_no"] == 1
    assert versions[0]["name"] == "社保纳税复核"
    assert versions[0]["rule_type"] == "tighten_rule"
    assert "检查企业纳税证明和社保证明" in versions[0]["description"]
    assert versions[0]["edit_reason"] == "补充证据缺失时不得自动符合的约束"


def test_custom_rule_can_rollback_to_previous_version() -> None:
    import sqlite3

    asyncio.run(init_db())
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM rule_versions WHERE rule_id = 'custom.rollback.demo'")
        conn.execute("DELETE FROM custom_rules WHERE id = 'custom.rollback.demo'")
        conn.execute(
            """INSERT INTO custom_rules
               (id, source_draft_id, name, rule_type, description, enabled, created_at, updated_at)
               VALUES ('custom.rollback.demo', 9301, '当前规则：过严社保纳税复核', 'required_evidence_rule',
                       '当前版本要求所有材料必须逐项完整，否则全部不符合。', 1,
                       '2026-07-02 15:00:00', '2026-07-02 15:10:00')"""
        )
        conn.execute(
            """INSERT INTO rule_versions
               (rule_id, version_no, name, rule_type, description, edit_reason, created_at)
               VALUES ('custom.rollback.demo', 1, '原规则：社保纳税复核', 'tighten_rule',
                       '原版本只把证据不足降级为需确认。', '修改前版本', '2026-07-02 15:05:00')"""
        )
        conn.commit()

    client = TestClient(app)
    resp = client.put(
        "/api/v1/rules/custom.rollback.demo/rollback",
        json={"version_no": 1, "reason": "当前版本过严，恢复为需确认策略"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "原规则：社保纳税复核"
    assert body["data"]["rule_type"] == "tighten_rule"
    assert "需确认" in body["data"]["description"]

    versions = client.get("/api/v1/rules/custom.rollback.demo/versions").json()["data"]
    assert versions[0]["version_no"] == 2
    assert versions[0]["name"] == "当前规则：过严社保纳税复核"
    assert "回滚到 v1" in versions[0]["edit_reason"]
    assert "当前版本过严" in versions[0]["edit_reason"]


def test_approving_rule_draft_publishes_custom_rule() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]

    resp = client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过，先作为自定义规则发布"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["draft_status"] == "published"

    rules = client.get("/api/v1/rules").json()["data"]
    custom = next(item for item in rules if item["id"].startswith("custom.rule_draft."))
    assert custom["name"] == draft["name"]
    assert custom["source"] == "规则草案"
    assert custom["enabled"] is True
    assert "社保证明" in custom["description"]


def test_published_custom_rule_can_be_disabled() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]
    client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "published", "review_reason": "审核通过"},
    )
    custom_rule_id = f"custom.rule_draft.{draft['id']}"

    resp = client.put(
        f"/api/v1/rules/{custom_rule_id}/enabled",
        json={"enabled": False, "reason": "发布后发现样本不足，临时停用"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == custom_rule_id
    assert body["data"]["enabled"] is False
    rules = client.get("/api/v1/rules").json()["data"]
    custom = next(item for item in rules if item["id"] == custom_rule_id)
    assert custom["enabled"] is False
    changes = client.get("/api/v1/rules/changes?limit=5").json()["data"]
    latest = changes[0]
    assert latest["rule_id"] == custom_rule_id
    assert latest["previous_enabled"] is True
    assert latest["new_enabled"] is False
    assert latest["reason"] == "发布后发现样本不足，临时停用"


def test_rejecting_rule_draft_does_not_publish_custom_rule() -> None:
    asyncio.run(init_db())
    _seed_match_correction_for_suggestion()
    client = TestClient(app)
    client.put(
        "/api/v1/rules/suggestions/correction-1/review",
        json={"review_status": "accepted", "review_reason": "补充税收和社保组合核验规则"},
    )
    draft = client.get("/api/v1/rules/drafts?limit=20").json()["data"][0]

    resp = client.put(
        f"/api/v1/rules/drafts/{draft['id']}/review",
        json={"draft_status": "rejected", "review_reason": "证据样本不足"},
    )

    assert resp.status_code == 200
    drafts = client.get("/api/v1/rules/drafts?limit=20").json()["data"]
    updated = next(item for item in drafts if item["id"] == draft["id"])
    assert updated["draft_status"] == "rejected"
    assert updated["review_reason"] == "证据样本不足"
    rules = client.get("/api/v1/rules").json()["data"]
    assert not any(item["id"] == f"custom.rule_draft.{draft['id']}" for item in rules)


if __name__ == "__main__":
    test_rule_catalog_api_returns_builtin_rules()
    test_rule_templates_api_returns_common_tender_analysis_templates()
    test_rule_template_can_create_pending_rule_draft()
    test_rule_template_reuses_existing_pending_draft()
    test_rule_catalog_api_updates_enabled_state()
    test_rule_catalog_api_records_enabled_change_reason()
    test_rule_suggestions_api_returns_correction_based_candidates()
    test_rule_suggestions_skip_low_quality_correction_reason()
    test_rule_suggestion_review_updates_status_and_reason()
    test_accepting_rule_suggestion_creates_rule_draft()
    test_pending_rule_draft_can_be_updated_before_publish()
    test_published_rule_draft_cannot_be_updated()
    test_rule_draft_similar_api_returns_existing_custom_rule()
    test_rule_draft_can_reuse_existing_rule_without_publishing_duplicate()
    test_publishing_similar_rule_records_difference_reason()
    test_rule_relations_api_returns_traceable_rule_links()
    test_custom_rule_can_be_merged_into_existing_rule()
    test_custom_rule_update_records_previous_version()
    test_custom_rule_can_rollback_to_previous_version()
    test_approving_rule_draft_publishes_custom_rule()
    test_published_custom_rule_can_be_disabled()
    test_rejecting_rule_draft_does_not_publish_custom_rule()
    print("rule library api tests passed")
