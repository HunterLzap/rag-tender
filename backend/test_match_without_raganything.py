"""匹配引擎不应依赖 RAG-Anything 旧链路。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
from app.database import init_db
from app.models.tender import TenderRequirement
from app.services.match_service import _match_performance_requirement, _semantic_match


def test_semantic_match_uses_sqlite_qualifications_without_raganything() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "match_without_rag.db")
        asyncio.run(_assert_sqlite_match())
    finally:
        tmp_dir.cleanup()


def test_performance_requirement_matches_performance_projects_without_llm() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "performance_match.db")
        asyncio.run(_assert_performance_match())
    finally:
        tmp_dir.cleanup()


def test_vague_performance_requirement_without_hard_fields_needs_review() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "performance_vague_match.db")
        asyncio.run(_assert_vague_performance_needs_review())
    finally:
        tmp_dir.cleanup()


def test_match_tender_uses_performance_projects_for_performance_requirements() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "performance_match_flow.db")
        asyncio.run(_assert_performance_match_flow())
    finally:
        tmp_dir.cleanup()


def test_match_tender_high_confidence_qualification_match_does_not_need_llm() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "qualification_match_flow.db")
        asyncio.run(_assert_high_confidence_qualification_match())
    finally:
        tmp_dir.cleanup()


def test_published_custom_tighten_rule_downgrades_auto_match_to_needs_review() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "custom_tighten_rule_match.db")
        asyncio.run(_assert_custom_tighten_rule_downgrades_match())
    finally:
        tmp_dir.cleanup()


def test_high_confidence_qualification_with_missing_evidence_needs_review() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "qualification_missing_evidence.db")
        asyncio.run(_assert_missing_evidence_needs_review())
    finally:
        tmp_dir.cleanup()


def test_tax_and_social_security_requirement_needs_both_evidence() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "tax_social_security.db")
        asyncio.run(_assert_tax_and_social_security_needs_both_evidence())
    finally:
        tmp_dir.cleanup()


def test_confirm_match_records_correction_case() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "match_correction.db")
        asyncio.run(_assert_confirm_match_records_correction())
    finally:
        tmp_dir.cleanup()


def test_confirm_match_requires_correction_reason() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "match_correction_reason_required.db")
        asyncio.run(_assert_confirm_match_requires_reason())
    finally:
        tmp_dir.cleanup()


def test_list_match_corrections_returns_display_context() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "match_correction_list.db")
        asyncio.run(_assert_list_match_corrections())
    finally:
        tmp_dir.cleanup()


def test_semantic_match_common_procurement_phrases_to_existing_qualifications() -> None:
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        database.DB_PATH = str(Path(tmp_dir.name) / "common_phrase_match.db")
        asyncio.run(_assert_common_procurement_phrase_match())
    finally:
        tmp_dir.cleanup()


async def _assert_sqlite_match() -> None:
    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO qualifications
               (name, number, scope, category, status, holder, created_at)
               VALUES (?, ?, ?, ?, ?, ?, '2026-06-29 10:00:00')""",
            (
                "特种作业操作证（低压电工作业）",
                "A31000032323073858",
                "低压电工作业",
                "personnel",
                "valid",
                "刘伟",
            ),
        )
        await db.commit()
    finally:
        await db.close()

    req = TenderRequirement(
        id=1,
        tender_id=1,
        category="personnel",
        requirement_nature="capability",
        title="电工证要求",
        content="拟派人员须具备低压电工作业证。",
        is_hard=True,
    )

    qual_id, score, reason = await _semantic_match(1, req)

    assert qual_id == 1
    assert score >= 0.7
    assert "SQLite" in reason


async def _assert_performance_match() -> None:
    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO performance_projects
               (project_name, client_name, contract_amount, project_scope, year, file_ids, remark, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, '2026-06-30 09:00:00', '2026-06-30 09:00:00')""",
            (
                "交大医学院",
                "武汉华康世纪医疗股份有限公司",
                "60万",
                "强弱电一体柜；地点：上海",
                "2026",
                "[189]",
                "自动从年度业绩表解析",
            ),
        )
        await db.execute(
            """INSERT INTO performance_projects
               (project_name, client_name, contract_amount, project_scope, year, file_ids, remark, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, '2026-06-30 09:00:00', '2026-06-30 09:00:00')""",
            (
                "阿里数据中心",
                "镇江鸿鑫智能制造装备有限公司",
                "49万",
                "变频动力柜；地点：河北",
                "2026",
                "[189]",
                "自动从年度业绩表解析",
            ),
        )
        await db.commit()
    finally:
        await db.close()

    req = TenderRequirement(
        id=1,
        tender_id=1,
        category="performance",
        requirement_nature="capability",
        title="类似项目业绩",
        content="投标人须提供近三年类似项目业绩，合同金额不低于50万元。",
        is_hard=True,
    )

    result = await _match_performance_requirement(req)

    assert result["status"] == "matched"
    assert result["in_knowledge_base"] is True
    assert result["similarity_score"] >= 0.7
    assert "交大医学院" in result["reason"]
    assert "60万" in result["reason"]


async def _assert_vague_performance_needs_review() -> None:
    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO performance_projects
               (project_name, client_name, contract_amount, project_scope, year, file_ids, remark, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, '2026-06-30 09:00:00', '2026-06-30 09:00:00')""",
            (
                "交大医学院",
                "武汉华康世纪医疗股份有限公司",
                "60万",
                "强弱电一体柜；地点：上海",
                "2026",
                "[189]",
                "自动从年度业绩表解析",
            ),
        )
        await db.commit()
    finally:
        await db.close()

    req = TenderRequirement(
        id=1,
        tender_id=1,
        category="performance",
        requirement_nature="capability",
        title="真实有效业绩",
        content="投标人须提供真实有效业绩。",
        is_hard=True,
    )

    result = await _match_performance_requirement(req)

    assert result["status"] == "needs_review"
    assert result["in_knowledge_base"] is True
    assert "缺少可自动核验字段" in result["reason"]
    assert any(item.check_key == "performance_relevance" and item.status == "unknown" for item in result["evidence_items"])


async def _assert_performance_match_flow() -> None:
    from app.services.match_service import match_tender

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (99, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 99, 'performance', 'capability', '类似业绩',
                       '投标人须提供近三年类似项目业绩，合同金额不低于50万元。', 1,
                       '投标人须提供近三年类似项目业绩，合同金额不低于50万元。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO performance_projects
               (project_name, client_name, contract_amount, project_scope, year, file_ids, remark, created_at, updated_at)
               VALUES ('交大医学院', '武汉华康世纪医疗股份有限公司', '60万',
                       '强弱电一体柜；地点：上海', '2026', '[189]',
                       '自动从年度业绩表解析', '2026-06-30 09:00:00', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    results = await match_tender(99)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].qualification_id is None
    assert results[0].in_knowledge_base is True
    assert "交大医学院" in (results[0].reason or "")

    db = await database.get_db()
    try:
        cursor = await db.execute("SELECT status, reason FROM match_results WHERE tender_id = 99")
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["status"] == "matched"
    assert "交大医学院" in row["reason"]


async def _assert_high_confidence_qualification_match() -> None:
    from app.services.match_service import match_tender

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (100, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 100, 'personnel', 'capability', '电工证要求',
                       '拟派人员须具备低压电工作业证。', 1,
                       '拟派人员须具备低压电工作业证。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, number, scope, category, status, holder, created_at)
               VALUES (1, '特种作业操作证（低压电工作业）', 'A31000032323073858',
                       '低压电工作业', 'personnel', 'valid', '刘伟', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    results = await match_tender(100)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].qualification_id == 1
    assert "字段级证据核验通过" in (results[0].reason or "")
    assert any(item.check_key == "certificate_type" and item.status == "pass" for item in results[0].evidence_items)
    assert any(item.check_key == "holder" and item.status == "pass" for item in results[0].evidence_items)


async def _assert_custom_tighten_rule_downgrades_match() -> None:
    from app.services.match_service import get_match_results, match_tender

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (110, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 110, 'personnel', 'capability', '电工证要求',
                       '拟派人员须具备低压电工作业证。', 1,
                       '拟派人员须具备低压电工作业证。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, number, scope, category, status, holder, created_at)
               VALUES (1, '特种作业操作证（低压电工作业）', 'A31000032323073858',
                       '低压电工作业', 'personnel', 'valid', '刘伟', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO custom_rules
               (id, source_draft_id, name, rule_type, description, enabled, created_at, updated_at)
               VALUES ('custom.rule_draft.1', 1, '低压电工作业证复核规则', 'tighten_rule',
                       '低压电工作业证要求即使系统字段级证据通过，也必须转为待确认，由人工核认证书原件。',
                       1, '2026-06-30 09:00:00', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    results = await match_tender(110)

    assert len(results) == 1
    assert results[0].status == "needs_review"
    assert results[0].qualification_id == 1
    assert "自定义收紧规则" in (results[0].reason or "")
    assert any(item.check_key == "custom_rule:custom.rule_draft.1" for item in results[0].evidence_items)

    persisted = await get_match_results(110)
    assert persisted[0].status == "needs_review"
    assert any(item.check_key == "custom_rule:custom.rule_draft.1" for item in persisted[0].evidence_items)


async def _assert_missing_evidence_needs_review() -> None:
    from app.services.match_service import get_match_results, match_tender

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (101, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 101, 'qualification', 'capability', 'ISO9001认证',
                       '投标人须具有有效期内ISO9001质量管理体系认证，认证范围覆盖相关服务。', 1,
                       '投标人须具有有效期内ISO9001质量管理体系认证，认证范围覆盖相关服务。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, scope, category, status, holder, created_at)
               VALUES (1, 'ISO9001质量管理体系认证证书', '', 'enterprise', 'valid',
                       '上海苏靖机电工程有限公司', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    results = await match_tender(101)

    assert len(results) == 1
    assert results[0].status == "needs_review"
    assert results[0].qualification_id == 1
    assert any(item.check_key == "expiry_date" and item.status == "unknown" for item in results[0].evidence_items)
    assert any(item.check_key == "scope" and item.status == "unknown" for item in results[0].evidence_items)

    persisted = await get_match_results(101)
    assert persisted[0].status == "needs_review"
    assert any(item.check_key == "scope" and item.status == "unknown" for item in persisted[0].evidence_items)


async def _assert_tax_and_social_security_needs_both_evidence() -> None:
    from app.services.match_service import match_tender

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (103, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 103, 'financial', 'capability', '依法缴纳税收和社保',
                       '投标人须有依法缴纳税收和社会保障资金的良好记录。', 1,
                       '投标人须有依法缴纳税收和社会保障资金的良好记录。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, scope, category, status, holder, created_at)
               VALUES (1, '纳税证明', '纳税/完税证明', 'financial', 'valid',
                       '上海苏靖机电工程有限公司', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    results = await match_tender(103)

    assert len(results) == 1
    assert results[0].status == "needs_review"
    assert any(item.check_key == "tax_payment" and item.status == "pass" for item in results[0].evidence_items)
    assert any(item.check_key == "social_security" and item.status == "unknown" for item in results[0].evidence_items)


async def _assert_confirm_match_records_correction() -> None:
    from app.services.match_service import confirm_match

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (102, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 102, 'qualification', 'capability', 'ISO9001认证',
                       '投标人须具有有效期内ISO9001质量管理体系认证。', 1,
                       '投标人须具有有效期内ISO9001质量管理体系认证。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO match_results
               (id, tender_id, requirement_id, status, reason, in_knowledge_base,
                similarity_score, evidence_items, created_at)
               VALUES (1, 102, 1, 'needs_review', '字段级证据不完整', 1,
                       0.82, '[]', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    result = await confirm_match(1, "unmatched", "认证范围不覆盖本项目服务内容")

    assert result is not None
    assert result.confirmed_status == "unmatched"

    db = await database.get_db()
    try:
        cursor = await db.execute(
            """SELECT match_id, tender_id, requirement_id, previous_status,
                      confirmed_status, correction_reason
               FROM match_corrections WHERE match_id = ?""",
            (1,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row is not None
    assert row["tender_id"] == 102
    assert row["requirement_id"] == 1
    assert row["previous_status"] == "needs_review"
    assert row["confirmed_status"] == "unmatched"
    assert row["correction_reason"] == "认证范围不覆盖本项目服务内容"


async def _assert_confirm_match_requires_reason() -> None:
    from app.services.match_service import confirm_match

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (103, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 103, 'qualification', 'capability', 'ISO9001认证',
                       '投标人须具有有效期内ISO9001质量管理体系认证。', 1,
                       '投标人须具有有效期内ISO9001质量管理体系认证。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO match_results
               (id, tender_id, requirement_id, status, reason, in_knowledge_base,
                similarity_score, evidence_items, created_at)
               VALUES (1, 103, 1, 'needs_review', '字段级证据不完整', 1,
                       0.82, '[]', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    result = await confirm_match(1, "unmatched", "  ")

    assert result is None

    db = await database.get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS count FROM match_corrections")
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["count"] == 0


async def _assert_list_match_corrections() -> None:
    from app.services.match_service import list_match_corrections

    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (id, filename, original_path, title, status, created_at)
               VALUES (104, '测试标书.pdf', 'test.pdf', '测试标书', 'completed', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO tender_requirements
               (id, tender_id, category, requirement_nature, title, content, is_hard, raw_text, created_at)
               VALUES (1, 104, 'qualification', 'capability', 'ISO9001认证',
                       '投标人须具有有效期内ISO9001质量管理体系认证。', 1,
                       '投标人须具有有效期内ISO9001质量管理体系认证。',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, scope, category, status, holder, created_at)
               VALUES (1, 'ISO9001质量管理体系认证证书', '自动化控制设备开发',
                       'enterprise', 'valid', '上海苏靖机电工程有限公司',
                       '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO match_corrections
               (id, match_id, tender_id, requirement_id, qualification_id, previous_status,
                confirmed_status, correction_reason, evidence_snapshot, created_at)
               VALUES (1, 1, 104, 1, 1, 'needs_review', 'unmatched',
                       '认证范围不覆盖本项目服务内容', '[]', '2026-07-01 16:30:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    rows = await list_match_corrections(limit=20)

    assert len(rows) == 1
    assert rows[0]["tender_title"] == "测试标书"
    assert rows[0]["requirement_title"] == "ISO9001认证"
    assert rows[0]["qualification_name"] == "ISO9001质量管理体系认证证书"
    assert rows[0]["previous_status"] == "needs_review"
    assert rows[0]["confirmed_status"] == "unmatched"
    assert rows[0]["correction_reason"] == "认证范围不覆盖本项目服务内容"


async def _assert_common_procurement_phrase_match() -> None:
    await init_db()
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO qualifications
               (id, name, scope, category, status, holder, created_at)
               VALUES (1, '质量管理体系认证证书', '自动化控制设备开发', 'enterprise', 'valid',
                       '上海苏靖机电工程有限公司', '2026-06-30 09:00:00')"""
        )
        await db.execute(
            """INSERT INTO qualifications
               (id, name, scope, category, status, holder, created_at)
               VALUES (2, '纳税证明', '纳税/完税证明', 'financial', 'valid',
                       '上海苏靖机电工程有限公司', '2026-06-30 09:00:00')"""
        )
        await db.commit()
    finally:
        await db.close()

    system_req = TenderRequirement(
        id=1,
        tender_id=1,
        category="qualification",
        requirement_nature="capability",
        title="管理体系认证（评分项）",
        content="投标单位具有有效的质量管理体系认证、环境管理体系认证证书。",
        is_hard=True,
    )
    tax_req = TenderRequirement(
        id=2,
        tender_id=1,
        category="qualification",
        requirement_nature="capability",
        title="依法纳税和社保",
        content="有依法缴纳税收和社会保障资金的良好记录。",
        is_hard=True,
    )

    system_qual_id, system_score, _ = await _semantic_match(1, system_req)
    tax_qual_id, tax_score, _ = await _semantic_match(1, tax_req)

    assert system_qual_id == 1
    assert system_score >= 0.7
    assert tax_qual_id == 2
    assert tax_score >= 0.7


if __name__ == "__main__":
    test_semantic_match_uses_sqlite_qualifications_without_raganything()
    test_performance_requirement_matches_performance_projects_without_llm()
    test_vague_performance_requirement_without_hard_fields_needs_review()
    test_match_tender_uses_performance_projects_for_performance_requirements()
    test_match_tender_high_confidence_qualification_match_does_not_need_llm()
    test_published_custom_tighten_rule_downgrades_auto_match_to_needs_review()
    test_high_confidence_qualification_with_missing_evidence_needs_review()
    test_tax_and_social_security_requirement_needs_both_evidence()
    test_confirm_match_records_correction_case()
    test_confirm_match_requires_correction_reason()
    test_list_match_corrections_returns_display_context()
    test_semantic_match_common_procurement_phrases_to_existing_qualifications()
    print("match without raganything tests passed")
