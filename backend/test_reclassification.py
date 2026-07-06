"""标书要求分类改造测试套件（T01-T05 验证）。

覆盖六大测试维度：
1. 匹配分流逻辑 _should_match() 单元测试
2. 数据库迁移幂等性测试
3. 技术响应 Service CRUD 测试
4. 待办清单 Service CRUD 测试
5. LLM Prompt 格式验证
6. 回归测试（5 类数值规则不破坏）

运行方式：
    cd backend
    .venv/Scripts/python.exe test_reclassification.py

或（如已安装 pytest）：
    .venv/Scripts/python.exe -m pytest test_reclassification.py -v

测试不依赖外部服务（LLM/RAG），数据库使用临时文件。
"""

import asyncio
import os
import sys
import tempfile
import traceback
from unittest.mock import patch

# 将 backend 目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ===========================================================================
# 全局测试统计
# ===========================================================================
_passed = 0
_failed = 0
_failures: list[str] = []


def _check(condition: bool, test_name: str, detail: str = "") -> None:
    """断言辅助：记录通过/失败。"""
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {test_name}")
    else:
        _failed += 1
        msg = f"  [FAIL] {test_name}" + (f" — {detail}" if detail else "")
        print(msg)
        _failures.append(f"{test_name}: {detail}")


# ===========================================================================
# 数据库临时环境管理
# ===========================================================================

_temp_db_path: str = ""


def _setup_temp_db() -> str:
    """创建临时 SQLite 文件并 patch DB_PATH。返回临时文件路径。"""
    global _temp_db_path
    fd, _temp_db_path = tempfile.mkstemp(suffix=".db", prefix="test_reclass_")
    os.close(fd)
    # patch database 模块中的 DB_PATH（get_db 和 init_db 都引用此变量）
    import app.database as db_module
    db_module.DB_PATH = _temp_db_path
    return _temp_db_path


def _teardown_temp_db() -> None:
    """删除临时数据库文件。"""
    global _temp_db_path
    if _temp_db_path and os.path.exists(_temp_db_path):
        try:
            os.remove(_temp_db_path)
        except OSError:
            pass


async def _seed_tender_and_requirements(db, tender_id: int, reqs: list[dict]) -> None:
    """向数据库插入标书记录和要求记录。

    Args:
        db: aiosqlite 连接。
        tender_id: 标书 ID。
        reqs: 要求字典列表，每项含 category/requirement_nature/title/content 等。
    """
    now = "2026-06-25 10:00:00"
    await db.execute(
        """INSERT INTO tenders (id, filename, original_path, title, file_type,
           status, upload_time, created_at)
           VALUES (?, ?, ?, ?, 'pdf', 'completed', ?, ?)""",
        (tender_id, f"test_{tender_id}.pdf", f"/tmp/test_{tender_id}.pdf",
         f"测试标书{tender_id}", now, now),
    )
    for r in reqs:
        await db.execute(
            """INSERT INTO tender_requirements
               (tender_id, category, requirement_nature, title, content,
                is_hard, raw_text, page_number, numeric_value, numeric_operator,
                numeric_unit, review_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tender_id, r.get("category", "other"),
             r.get("requirement_nature", "capability"),
             r.get("title"), r.get("content"),
             1 if r.get("is_hard", True) else 0,
             r.get("raw_text", ""), r.get("page_number"),
             r.get("numeric_value"), r.get("numeric_operator"),
             r.get("numeric_unit"), "pending", now),
        )
    await db.commit()


# ===========================================================================
# 1. 匹配分流逻辑测试（P0-R3 核心）
# ===========================================================================

def test_should_match() -> None:
    """测试 _should_match() 分流函数覆盖所有 category x nature 组合。"""
    print("\n" + "=" * 60)
    print("  1. 匹配分流逻辑测试 (_should_match)")
    print("=" * 60)

    from app.services.match_service import _should_match
    from app.models.tender import TenderRequirement

    def _make_req(
        category: str,
        nature: str = "capability",
        title: str = "test",
        content: str = "test",
    ) -> TenderRequirement:
        return TenderRequirement(
            id=1, tender_id=1, category=category,
            requirement_nature=nature, title=title, content=content,
        )

    # qualification + capability → True（走匹配）
    _check(
        _should_match(_make_req("qualification", "capability")) is True,
        "qualification + capability → True",
    )

    # performance + capability → True
    _check(
        _should_match(_make_req("performance", "capability")) is True,
        "performance + capability → True",
    )

    # performance + submission → False（走待办清单）
    _check(
        _should_match(_make_req("performance", "submission")) is False,
        "performance + submission → False",
    )

    # product_spec → False（走技术响应表，无论 nature）
    _check(
        _should_match(_make_req("product_spec", "capability")) is False,
        "product_spec + capability → False",
    )
    _check(
        _should_match(_make_req("product_spec", "submission")) is False,
        "product_spec + submission → False",
    )

    # submission category → False
    _check(
        _should_match(_make_req("submission", "submission")) is False,
        "submission + submission → False",
    )

    # financial + submission → False
    _check(
        _should_match(_make_req("financial", "submission")) is False,
        "financial + submission → False",
    )

    # personnel + capability → True
    _check(
        _should_match(_make_req("personnel", "capability")) is True,
        "personnel + capability → True",
    )

    # other + capability → False（不属于资质库证明范围）
    _check(
        _should_match(_make_req("other", "capability")) is False,
        "other + capability → False",
    )

    # other + submission → False
    _check(
        _should_match(_make_req("other", "submission")) is False,
        "other + submission → False",
    )

    # financial + capability → True
    _check(
        _should_match(_make_req("financial", "capability")) is True,
        "financial + capability → True",
    )

    # 泛化声明/信用/投标规则类要求不走资质库匹配
    _check(
        _should_match(
            _make_req(
                "qualification",
                "capability",
                title="无重大违法记录",
                content="参加政府采购活动前三年内，在经营活动中没有重大违法记录",
            )
        )
        is False,
        "无重大违法记录 → False",
    )
    _check(
        _should_match(
            _make_req(
                "financial",
                "capability",
                title="投标报价不超最高限价",
                content="投标报价低于或等于财政预算价格或最高限价",
            )
        )
        is False,
        "投标报价规则 → False",
    )

    # 旧数据兼容：requirement_nature 缺失时默认 capability → True
    # TenderRequirement 模型默认 requirement_nature="capability"
    old_req = TenderRequirement(
        id=1, tender_id=1, category="qualification",
        title="test", content="test",
        # 不传 requirement_nature，使用默认值
    )
    _check(
        _should_match(old_req) is True,
        "旧数据兼容（nature 缺省=capability）→ True",
        f"requirement_nature={old_req.requirement_nature}",
    )


# ===========================================================================
# 2. 数据库迁移幂等性测试
# ===========================================================================

async def _test_db_migration_idempotent() -> None:
    """测试 init_db() 多次执行不报错，且表/列存在。"""
    print("\n" + "=" * 60)
    print("  2. 数据库迁移幂等性测试")
    print("=" * 60)

    import aiosqlite
    import app.database as db_module

    # 第一次 init_db
    try:
        await db_module.init_db()
        _check(True, "init_db() 第一次执行不报错")
    except Exception as e:
        _check(False, "init_db() 第一次执行不报错", str(e))
        return

    # 第二次 init_db（幂等性）
    try:
        await db_module.init_db()
        _check(True, "init_db() 第二次执行不报错（幂等）")
    except Exception as e:
        _check(False, "init_db() 第二次执行不报错（幂等）", str(e))

    # 第三次 init_db（充分验证幂等）
    try:
        await db_module.init_db()
        _check(True, "init_db() 第三次执行不报错（幂等）")
    except Exception as e:
        _check(False, "init_db() 第三次执行不报错（幂等）", str(e))

    db_path = db_module.DB_PATH

    # 验证 tender_requirements 表有 requirement_nature 列
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(tender_requirements)")
        columns = [row[1] for row in await cursor.fetchall()]
    _check(
        "requirement_nature" in columns,
        "tender_requirements 表有 requirement_nature 列",
        f"columns={columns}",
    )

    # 验证 technical_responses 表存在
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='technical_responses'"
        )
        row = await cursor.fetchone()
    _check(
        row is not None,
        "technical_responses 表存在",
    )

    # 验证 submission_checklist 表存在
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='submission_checklist'"
        )
        row = await cursor.fetchone()
    _check(
        row is not None,
        "submission_checklist 表存在",
    )

    # 验证 technical_responses 表有 response_status 列（迁移添加）
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(technical_responses)")
        columns = [row[1] for row in await cursor.fetchall()]
    _check(
        "response_status" in columns,
        "technical_responses 表有 response_status 列",
        f"columns={columns}",
    )


# ===========================================================================
# 3. 技术响应 Service 测试
# ===========================================================================

async def _test_technical_response_service() -> None:
    """测试技术响应 Service 的 init/get_all/update/batch_update。"""
    print("\n" + "=" * 60)
    print("  3. 技术响应 Service 测试")
    print("=" * 60)

    import aiosqlite
    import app.database as db_module
    from app.services import technical_response_service as svc
    from app.schemas.technical import TechnicalResponseUpdate, TechnicalResponseBatchUpdate, TechnicalResponseBatchItem

    db_path = db_module.DB_PATH

    # 准备数据：创建标书 + 含 product_spec 要求
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _seed_tender_and_requirements(db, 1001, [
            {"category": "product_spec", "requirement_nature": "capability",
             "title": "输出功率", "content": "输出功率≥200kW",
             "numeric_value": "200", "numeric_operator": ">=", "numeric_unit": "kW"},
            {"category": "product_spec", "requirement_nature": "capability",
             "title": "防护等级", "content": "防护等级≥IP65",
             "numeric_value": "IP65", "numeric_operator": ">=", "numeric_unit": ""},
            {"category": "qualification", "requirement_nature": "capability",
             "title": "营业执照", "content": "具有营业执照"},
        ])

    # init_from_requirements — 应从 product_spec 要求生成 2 条记录
    created = await svc.init_from_requirements(1001)
    _check(
        len(created) == 2,
        "init_from_requirements 生成 2 条（product_spec 要求）",
        f"actual={len(created)}",
    )

    # required_value 派生：有 numeric 时拼接
    power_resp = next((r for r in created if "功率" in (r.spec_name or "")), None)
    _check(
        power_resp is not None and "200" in (power_resp.required_value or ""),
        "required_value 派生含 numeric_value（200kW）",
        f"required_value={power_resp.required_value if power_resp else 'N/A'}",
    )
    _check(
        power_resp is not None and ">=200kW" == (power_resp.required_value or ""),
        "required_value = '>=200kW'（operator+value+unit 拼接）",
        f"required_value={power_resp.required_value if power_resp else 'N/A'}",
    )

    # init_from_requirements 幂等性：再次调用不重复创建
    created_again = await svc.init_from_requirements(1001)
    _check(
        len(created_again) == 0,
        "init_from_requirements 幂等（再次调用返回空）",
        f"actual={len(created_again)}",
    )

    # get_all — 返回 2 条
    all_resp = await svc.get_all(1001)
    _check(
        len(all_resp) == 2,
        "get_all 返回 2 条技术响应",
        f"actual={len(all_resp)}",
    )

    # update — 更新 actual_value / response_status / remark
    resp_id = all_resp[0].id
    update_data = TechnicalResponseUpdate(
        actual_value="220kW",
        response_status="met",
        remark="优于要求",
    )
    updated = await svc.update(resp_id, update_data)
    _check(
        updated is not None and updated.actual_value == "220kW",
        "update actual_value → '220kW'",
        f"actual_value={updated.actual_value if updated else 'N/A'}",
    )
    _check(
        updated is not None and updated.response_status == "met",
        "update response_status → 'met'",
        f"response_status={updated.response_status if updated else 'N/A'}",
    )
    _check(
        updated is not None and updated.remark == "优于要求",
        "update remark → '优于要求'",
        f"remark={updated.remark if updated else 'N/A'}",
    )

    # 验证更新后能读回
    all_after = await svc.get_all(1001)
    read_back = next((r for r in all_after if r.id == resp_id), None)
    _check(
        read_back is not None and read_back.actual_value == "220kW",
        "更新后 get_all 能读回 actual_value='220kW'",
    )

    # batch_update — 注意源码接受 list[dict]，需将 Pydantic 模型转为 dict
    batch_items = [
        {"id": all_resp[0].id, "actual_value": "225kW", "remark": "batch更新"},
        {"id": all_resp[1].id, "actual_value": "IP66", "remark": "batch更新2"},
    ]
    batch_result = await svc.batch_update(1001, batch_items)
    _check(
        len(batch_result) == 2,
        "batch_update 返回 2 条",
        f"actual={len(batch_result)}",
    )

    # required_value 派生：无 numeric 时取 content 摘要
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _seed_tender_and_requirements(db, 1002, [
            {"category": "product_spec", "requirement_nature": "capability",
             "title": "材质要求", "content": "设备外壳采用不锈钢304材质制造，耐腐蚀",
             "numeric_value": None, "numeric_operator": None, "numeric_unit": None},
        ])
    created2 = await svc.init_from_requirements(1002)
    _check(
        len(created2) == 1,
        "无 numeric 的 product_spec 也能生成技术响应",
    )
    if created2:
        rv = created2[0].required_value or ""
        _check(
            "不锈钢" in rv,
            "无 numeric 时 required_value 取 content 摘要",
            f"required_value={rv}",
        )


# ===========================================================================
# 4. 待办清单 Service 测试
# ===========================================================================

async def _test_submission_checklist_service() -> None:
    """测试待办清单 Service 的 init/get_all/update/add_manual_item。"""
    print("\n" + "=" * 60)
    print("  4. 待办清单 Service 测试")
    print("=" * 60)

    import aiosqlite
    import app.database as db_module
    from app.services import submission_checklist_service as svc
    from app.schemas.checklist import SubmissionChecklistUpdate, ManualItemCreate

    db_path = db_module.DB_PATH

    # 准备数据：标书 + 含 submission 类要求
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _seed_tender_and_requirements(db, 2001, [
            {"category": "submission", "requirement_nature": "submission",
             "title": "法人授权委托书", "content": "提交法人授权委托书原件"},
            {"category": "performance", "requirement_nature": "submission",
             "title": "业绩证明材料", "content": "提交近三年业绩证明材料"},
            {"category": "qualification", "requirement_nature": "capability",
             "title": "营业执照", "content": "具有营业执照"},
            {"category": "other", "requirement_nature": "submission",
             "title": "灰色地带项", "content": "【灰色地带】提交制造商授权书"},
        ])

    # init_from_requirements — 应从 submission 类要求生成 3 条
    created = await svc.init_from_requirements(2001)
    _check(
        len(created) == 3,
        "init_from_requirements 生成 3 条（submission 类要求）",
        f"actual={len(created)}",
    )

    # 灰色地带备注提示
    gray_item = next((r for r in created if "灰色" in (r.item_name or "")), None)
    if gray_item:
        _check(
            gray_item.remark is not None and "灰色地带" in gray_item.remark,
            "灰色地带项 remark 含提示",
            f"remark={gray_item.remark}",
        )
    else:
        _check(False, "灰色地带项存在", "未找到")

    # 幂等性
    created_again = await svc.init_from_requirements(2001)
    _check(
        len(created_again) == 0,
        "init_from_requirements 幂等（再次调用返回空）",
        f"actual={len(created_again)}",
    )

    # get_all — 返回 3 条
    all_items = await svc.get_all(2001)
    _check(
        len(all_items) == 3,
        "get_all 返回 3 条待办",
        f"actual={len(all_items)}",
    )

    # 状态默认 not_started
    _check(
        all(item.status == "not_started" for item in all_items),
        "所有待办初始状态为 not_started",
        f"statuses={[i.status for i in all_items]}",
    )

    # update — 更新 status
    item_id = all_items[0].id
    update_data = SubmissionChecklistUpdate(status="in_progress")
    updated = await svc.update(item_id, update_data)
    _check(
        updated is not None and updated.status == "in_progress",
        "update status → 'in_progress'",
        f"status={updated.status if updated else 'N/A'}",
    )

    # 更新为 done
    update_data2 = SubmissionChecklistUpdate(status="done")
    updated2 = await svc.update(item_id, update_data2)
    _check(
        updated2 is not None and updated2.status == "done",
        "update status → 'done'",
    )

    # 验证更新后读回
    all_after = await svc.get_all(2001)
    read_back = next((r for r in all_after if r.id == item_id), None)
    _check(
        read_back is not None and read_back.status == "done",
        "更新后 get_all 能读回 status='done'",
    )

    # update — 无效 status 应返回 None
    invalid_update = SubmissionChecklistUpdate(status="invalid_status")
    invalid_result = await svc.update(item_id, invalid_update)
    _check(
        invalid_result is None,
        "update 无效 status → 返回 None",
    )

    # add_manual_item — 手动新增
    manual_data = ManualItemCreate(
        item_name="打印装订投标文件",
        description="正本一份，副本五份",
        remark="注意盖章",
    )
    manual_item = await svc.add_manual_item(2001, manual_data)
    _check(
        manual_item is not None and manual_item.item_name == "打印装订投标文件",
        "add_manual_item 新增项名称正确",
        f"item_name={manual_item.item_name if manual_item else 'N/A'}",
    )
    _check(
        manual_item is not None and manual_item.status == "not_started",
        "手动新增项状态默认 not_started",
    )
    _check(
        manual_item is not None and manual_item.requirement_id is None,
        "手动新增项 requirement_id 为 None",
    )

    # 验证手动项出现在列表中
    all_final = await svc.get_all(2001)
    _check(
        len(all_final) == 4,
        "手动新增后 get_all 返回 4 条",
        f"actual={len(all_final)}",
    )


# ===========================================================================
# 5. LLM Prompt 格式测试
# ===========================================================================

def test_prompt_format() -> None:
    """验证 _EXTRACT_SYSTEM_PROMPT 包含三类分类定义、nature 字段、拆条规则、JSON schema。"""
    print("\n" + "=" * 60)
    print("  5. LLM Prompt 格式验证")
    print("=" * 60)

    from app.services.tender_service import _EXTRACT_SYSTEM_PROMPT

    prompt = _EXTRACT_SYSTEM_PROMPT

    # 验证包含三类分类定义
    _check(
        "product_spec" in prompt,
        "prompt 包含 product_spec 分类定义",
    )
    _check(
        "submission" in prompt,
        "prompt 包含 submission 分类定义",
    )
    _check(
        "qualification" in prompt,
        "prompt 包含 qualification 分类定义",
    )
    _check(
        "产品技术参数" in prompt,
        "prompt 包含 product_spec 中文说明",
    )
    _check(
        "投标待办提交件" in prompt,
        "prompt 包含 submission 中文说明",
    )

    # 验证包含 requirement_nature 字段说明
    _check(
        "requirement_nature" in prompt,
        "prompt 包含 requirement_nature 字段",
    )
    _check(
        "capability" in prompt,
        "prompt 包含 capability 取值说明",
    )

    # 验证包含拆条规则
    _check(
        "拆条" in prompt or "拆分" in prompt,
        "prompt 包含拆条规则",
    )

    # 验证 JSON 输出 schema 含 requirement_nature 字段
    _check(
        '"requirement_nature"' in prompt,
        "prompt JSON schema 含 requirement_nature 字段",
    )

    # 验证 REQUIREMENT_CATEGORIES 为 7 类
    from app.services.tender_service import REQUIREMENT_CATEGORIES
    expected = {
        "qualification", "product_spec", "submission",
        "performance", "financial", "personnel", "other",
    }
    _check(
        set(REQUIREMENT_CATEGORIES) == expected,
        "REQUIREMENT_CATEGORIES 为 7 类",
        f"actual={REQUIREMENT_CATEGORIES}",
    )
    _check(
        len(REQUIREMENT_CATEGORIES) == 7,
        "REQUIREMENT_CATEGORIES 数量为 7",
        f"len={len(REQUIREMENT_CATEGORIES)}",
    )

    # 验证 prompt 包含 few-shot 示例
    _check(
        "示例" in prompt,
        "prompt 包含 few-shot 示例",
    )


# ===========================================================================
# 6. 回归测试（现有功能不破坏）
# ===========================================================================

def test_regression() -> None:
    """验证 5 类数值规则模式仍可用，解析逻辑未变。"""
    print("\n" + "=" * 60)
    print("  6. 回归测试（5 类数值规则）")
    print("=" * 60)

    from app.services.match_service import (
        RULE_PATTERNS,
        _parse_numeric_from_requirement,
        _check_numeric_rule,
    )

    # 5 类规则模式存在
    expected_rules = {
        "registered_capital", "contract_amount", "revenue",
        "debt_ratio", "personnel_years",
    }
    _check(
        set(RULE_PATTERNS.keys()) == expected_rules,
        "5 类数值规则模式（RULE_PATTERNS）存在",
        f"actual={set(RULE_PATTERNS.keys())}",
    )

    # 注册资本解析
    result = _parse_numeric_from_requirement("注册资本≥500万元")
    _check(
        result is not None and result["rule_type"] == "registered_capital",
        "解析 '注册资本≥500万元' → registered_capital",
        f"result={result}",
    )
    _check(
        result is not None and result["value"] == 500.0,
        "注册资本数值 = 500.0",
        f"value={result['value'] if result else 'N/A'}",
    )

    # 合同金额解析
    result2 = _parse_numeric_from_requirement("合同金额≥200万元")
    _check(
        result2 is not None and result2["rule_type"] == "contract_amount",
        "解析 '合同金额≥200万元' → contract_amount",
    )

    # 营业收入解析
    result3 = _parse_numeric_from_requirement("营业收入≥1000万元")
    _check(
        result3 is not None and result3["rule_type"] == "revenue",
        "解析 '营业收入≥1000万元' → revenue",
    )

    # 资产负债率解析
    result4 = _parse_numeric_from_requirement("资产负债率≤75%")
    _check(
        result4 is not None and result4["rule_type"] == "debt_ratio",
        "解析 '资产负债率≤75%' → debt_ratio",
    )

    # 人员年限解析
    result5 = _parse_numeric_from_requirement("5年以上工作经验")
    _check(
        result5 is not None and result5["rule_type"] == "personnel_years",
        "解析 '5年以上' → personnel_years",
    )

    # _check_numeric_rule 逻辑验证
    # 满足场景：要求 >=500, 实际 1000
    req_numeric = {"value": 500.0, "operator": ">=", "unit": "万元"}
    satisfied, detail = _check_numeric_rule(req_numeric, 1000.0)
    _check(
        satisfied is True,
        "_check_numeric_rule: 1000 >= 500 → 满足",
        f"detail={detail}",
    )

    # 不满足场景：要求 >=500, 实际 200
    satisfied2, detail2 = _check_numeric_rule(req_numeric, 200.0)
    _check(
        satisfied2 is False,
        "_check_numeric_rule: 200 >= 500 → 不满足",
        f"detail={detail2}",
    )

    # qual_value 为 None → 不满足
    satisfied3, _ = _check_numeric_rule(req_numeric, None)
    _check(
        satisfied3 is False,
        "_check_numeric_rule: qual_value=None → 不满足",
    )

    # 运算符 <= 验证
    req_le = {"value": 75.0, "operator": "<=", "unit": "%"}
    satisfied4, _ = _check_numeric_rule(req_le, 60.0)
    _check(
        satisfied4 is True,
        "_check_numeric_rule: 60 <= 75 → 满足",
    )

    # ≥ 运算符兼容（替换为 >=）
    req_ge_unicode = {"value": 500.0, "operator": "≥", "unit": "万元"}
    satisfied5, _ = _check_numeric_rule(req_ge_unicode, 500.0)
    _check(
        satisfied5 is True,
        "_check_numeric_rule: ≥ 运算符兼容（500 ≥ 500 → 满足）",
    )

    # 空内容解析 → None
    _check(
        _parse_numeric_from_requirement("") is None,
        "空内容解析 → None",
    )
    _check(
        _parse_numeric_from_requirement("无数值要求") is None,
        "无数值内容解析 → None",
    )


# ===========================================================================
# 额外：去重 key 三元组逻辑验证
# ===========================================================================

def test_dedup_key() -> None:
    """验证拆条后去重 key 为 (raw_text, category, requirement_nature) 三元组。"""
    print("\n" + "=" * 60)
    print("  额外. 去重 key 三元组逻辑验证")
    print("=" * 60)

    # 模拟 _extract_requirements_from_text 中的去重逻辑
    seen_keys: set[tuple[str, str, str]] = set()
    all_reqs: list[dict] = []

    test_reqs = [
        # 拆条：同一 raw_text，不同 category + nature
        {"raw_text": "投标人须具有ISO9001认证并提供证书复印件",
         "category": "qualification", "requirement_nature": "capability",
         "title": "ISO9001认证"},
        {"raw_text": "投标人须具有ISO9001认证并提供证书复印件",
         "category": "submission", "requirement_nature": "submission",
         "title": "提供ISO9001证书复印件"},
        # 完全重复（应被去重）
        {"raw_text": "投标人须具有ISO9001认证并提供证书复印件",
         "category": "qualification", "requirement_nature": "capability",
         "title": "ISO9001认证（重复）"},
    ]

    for r in test_reqs:
        dedup_key = (
            (r.get("raw_text") or r.get("title") or "").strip(),
            r.get("category", "other").strip(),
            r.get("requirement_nature", "capability").strip(),
        )
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        all_reqs.append(r)

    _check(
        len(all_reqs) == 2,
        "拆条后 2 条保留（第 3 条重复被去重）",
        f"actual={len(all_reqs)}",
    )


# ===========================================================================
# 额外：reparse_requirements 清理逻辑验证
# ===========================================================================

async def _test_reparse_cleanup() -> None:
    """验证 reparse_requirements 清空所有关联表。"""
    print("\n" + "=" * 60)
    print("  额外. reparse_requirements 清理逻辑")
    print("=" * 60)

    import aiosqlite
    import app.database as db_module
    from app.services.tender_service import reparse_requirements
    from app.services.technical_response_service import init_from_requirements as tech_init
    from app.services.submission_checklist_service import init_from_requirements as checklist_init

    db_path = db_module.DB_PATH

    # 准备数据
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _seed_tender_and_requirements(db, 3001, [
            {"category": "product_spec", "requirement_nature": "capability",
             "title": "功率", "content": "功率≥200kW"},
            {"category": "submission", "requirement_nature": "submission",
             "title": "委托书", "content": "提交委托书"},
        ])

    # 生成技术响应和待办清单
    await tech_init(3001)
    await checklist_init(3001)

    # 插入一条 match_result
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO match_results
               (tender_id, requirement_id, status, reason, created_at)
               VALUES (?, ?, 'needs_review', 'test', '2026-06-25')""",
            (3001, 1),
        )
        await db.commit()

    # 验证数据存在
    async with aiosqlite.connect(db_path) as db:
        for table in ("tender_requirements", "match_results",
                       "technical_responses", "submission_checklist"):
            cursor = await db.execute(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE tender_id = ?", (3001,)
            )
            row = await cursor.fetchone()
            _check(
                row[0] > 0,
                f"reparse 前 {table} 有数据",
                f"count={row[0]}",
            )

    # 执行 reparse
    counts = await reparse_requirements(3001)

    # 验证全部清空
    async with aiosqlite.connect(db_path) as db:
        for table in ("tender_requirements", "match_results",
                       "technical_responses", "submission_checklist"):
            cursor = await db.execute(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE tender_id = ?", (3001,)
            )
            row = await cursor.fetchone()
            _check(
                row[0] == 0,
                f"reparse 后 {table} 清空",
                f"count={row[0]}",
            )


# ===========================================================================
# 主测试运行器
# ===========================================================================

def main() -> None:
    """主测试入口：执行所有测试并输出报告。"""
    print("=" * 60)
    print("  RAG-Tender Assistant 标书要求分类改造测试")
    print("  覆盖 T01-T05：匹配分流/迁移幂等/技术响应/待办清单/Prompt/回归")
    print("=" * 60)

    # 设置临时数据库
    _setup_temp_db()

    try:
        # ── 同步测试 ──
        test_should_match()
        test_prompt_format()
        test_regression()
        test_dedup_key()

        # ── 异步测试 ──
        asyncio.run(_test_db_migration_idempotent())
        asyncio.run(_test_technical_response_service())
        asyncio.run(_test_submission_checklist_service())
        asyncio.run(_test_reparse_cleanup())

    except Exception as e:
        print(f"\n  [ERROR] 测试执行异常: {e}")
        traceback.print_exc()
        global _failed
        _failed += 1
        _failures.append(f"测试执行异常: {e}")

    finally:
        _teardown_temp_db()

    # ── 总结 ──
    total = _passed + _failed
    print("\n" + "=" * 60)
    print(f"  测试总结: {total} 项 | 通过 {_passed} | 失败 {_failed}")
    print("=" * 60)

    if _failures:
        print("\n  失败详情:")
        for f in _failures:
            print(f"    - {f}")

    print()
    return _failed


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
