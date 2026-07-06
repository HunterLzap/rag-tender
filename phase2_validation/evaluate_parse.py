#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG-Tender Assistant Phase 2 — 解析效果评估脚本

基于标书样本的已知结构，对 test_parse.py 的输出 (parse_results.json) 进行评估。
本脚本不需要真实 API，做的是静态对照评估。

评估维度：
  1. 信息覆盖率（Coverage）：关键信息点是否被解析出来
  2. 表格结构保留率（Table Retention）：表格数据是否完整保留
  3. 数值准确性（Numeric Accuracy）：关键数值是否准确

评估清单（基于标书样本已知结构）：
  - 资质要求：7 项
  - 业绩要求：3 项
  - 财务要求：5 项
  - 人员要求：5 项
  - 评分标准：6 项
  - 供货清单：5 项
  - 技术参数表：14 行
  - 商务要求：关键数值

使用方法：
  python evaluate_parse.py                      # 评估 parse_results.json
  python evaluate_parse.py --file result.json   # 评估指定结果文件
  python evaluate_parse.py --checklist          # 只打印关键信息清单（不评估）
"""

import argparse
import json
import sys
from pathlib import Path


# ==================== 标书已知结构（Ground Truth）====================
# 基于样本文件 控制柜配电柜变频柜采购招标公告_样本.md 的已知信息

GROUND_TRUTH = {
    "project_info": {
        "description": "项目基本信息",
        "items": [
            {"id": "tender_no", "label": "招标编号", "value": "YB2024-01-RTA", "keywords": ["YB2024-01-RTA", "招标编号"]},
            {"id": "project_name", "label": "项目名称", "value": "控制柜、配电柜、变频柜采购项目", "keywords": ["控制柜", "配电柜", "变频柜", "采购项目"]},
            {"id": "delivery_period", "label": "交货期", "value": "30日", "keywords": ["30日", "交货期", "30 日"]},
            {"id": "consortium", "label": "联合体投标", "value": "不接受", "keywords": ["联合体", "不接受"]},
        ],
    },
    "qualification": {
        "description": "资质要求（硬性条件，7 项）",
        "items": [
            {"id": "q1", "label": "独立法人/营业执照", "keywords": ["营业执照", "法人", "三证合一"]},
            {"id": "q2", "label": "注册资本≥1000万", "keywords": ["注册资本", "1000万"]},
            {"id": "q3", "label": "经营范围（电气设备制造）", "keywords": ["经营范围", "电气设备", "输配电"]},
            {"id": "q4", "label": "ISO9001 质量管理体系", "keywords": ["ISO9001", "质量管理体系"]},
            {"id": "q5", "label": "ISO14001 环境管理体系", "keywords": ["ISO14001", "环境管理体系"]},
            {"id": "q6", "label": "ISO45001 职业健康安全", "keywords": ["ISO45001", "OHSAS18001", "职业健康"]},
            {"id": "q7", "label": "CCC/3C 强制认证", "keywords": ["CCC", "3C", "强制性产品认证"]},
        ],
    },
    "performance": {
        "description": "业绩要求（3 项）",
        "items": [
            {"id": "p1", "label": "近三年≥3个同类业绩", "keywords": ["3个", "近三年", "类似项目"]},
            {"id": "p2", "label": "单项合同≥200万", "keywords": ["200万", "合同金额"]},
            {"id": "p3", "label": "业绩证明材料", "keywords": ["合同首页", "签字页", "中标通知书"]},
        ],
    },
    "financial": {
        "description": "财务要求（5 项）",
        "items": [
            {"id": "f1", "label": "近三年无连续亏损", "keywords": ["财务状况", "亏损"]},
            {"id": "f2", "label": "三年审计报告", "keywords": ["审计报告", "资产负债表"]},
            {"id": "f3", "label": "营业收入≥3000万", "keywords": ["营业收入", "3000万"]},
            {"id": "f4", "label": "资产负债率≤70%", "keywords": ["资产负债率", "70%"]},
            {"id": "f5", "label": "银行资信证明", "keywords": ["银行资信", "资信证明"]},
        ],
    },
    "personnel": {
        "description": "人员要求（5 项）",
        "items": [
            {"id": "pe1", "label": "项目负责人-一级建造师", "keywords": ["项目负责人", "一级建造师"]},
            {"id": "pe2", "label": "技术负责人-高级工程师", "keywords": ["技术负责人", "高级工程师"]},
            {"id": "pe3", "label": "质量负责人-注册质量工程师", "keywords": ["质量负责人", "注册质量工程师"]},
            {"id": "pe4", "label": "安全负责人-注册安全工程师", "keywords": ["安全负责人", "注册安全工程师"]},
            {"id": "pe5", "label": "社保缴纳证明", "keywords": ["社保", "缴纳证明"]},
        ],
    },
    "scoring": {
        "description": "评分标准（6 项，满分 100）",
        "items": [
            {"id": "s1", "label": "投标报价 30分", "keywords": ["投标报价", "30"]},
            {"id": "s2", "label": "技术方案 25分", "keywords": ["技术方案", "25"]},
            {"id": "s3", "label": "设备性能 20分", "keywords": ["设备性能", "20"]},
            {"id": "s4", "label": "企业资质 10分", "keywords": ["企业资质", "10"]},
            {"id": "s5", "label": "项目团队 10分", "keywords": ["项目团队", "10"]},
            {"id": "s6", "label": "售后服务 5分", "keywords": ["售后服务", "5"]},
        ],
        "check_sum": 100,
    },
    "supply_list": {
        "description": "供货清单（5 项）",
        "items": [
            {"id": "sl1", "label": "自动化控制柜 6台", "keywords": ["自动化控制柜", "6"]},
            {"id": "sl2", "label": "变频柜 6套 55KW", "keywords": ["变频柜", "55KW", "6"]},
            {"id": "sl3", "label": "PLC柜 3台", "keywords": ["PLC", "3"]},
            {"id": "sl4", "label": "配电柜 4面 IP30", "keywords": ["配电柜", "4", "IP30"]},
            {"id": "sl5", "label": "控制柜附件 1批", "keywords": ["控制柜附件", "接线端子"]},
        ],
    },
    "tech_params": {
        "description": "技术参数表（关键参数）",
        "items": [
            {"id": "tp1", "label": "380V系统输入电压", "keywords": ["380", "415"]},
            {"id": "tp2", "label": "690V系统输入电压", "keywords": ["525", "690"]},
            {"id": "tp3", "label": "整流效率>97%", "keywords": ["97"]},
            {"id": "tp4", "label": "逆变效率>98.5%", "keywords": ["98.5"]},
            {"id": "tp5", "label": "防护等级IP20", "keywords": ["IP20"]},
            {"id": "tp6", "label": "输出频率0-300Hz", "keywords": ["0-300", "300"]},
        ],
    },
    "commercial": {
        "description": "商务要求关键数值",
        "items": [
            {"id": "c1", "label": "预付款30%", "keywords": ["预付款", "30%"]},
            {"id": "c2", "label": "到货款60%", "keywords": ["到货款", "60%"]},
            {"id": "c3", "label": "质保金10%", "keywords": ["质保金", "10%"]},
            {"id": "c4", "label": "质保期24个月", "keywords": ["24个月", "质量保证期"]},
            {"id": "c5", "label": "逾期违约金0.5%/日", "keywords": ["0.5%", "违约金"]},
            {"id": "c6", "label": "增值税13%", "keywords": ["13%", "增值税"]},
        ],
    },
}


# ==================== 评估逻辑 ====================

def evaluate_coverage(answer_text: str, category: dict) -> dict:
    """评估单个类别的信息覆盖率。

    Args:
        answer_text: RAG 返回的答案文本
        category: GROUND_TRUTH 中的某个类别

    Returns:
        包含覆盖率、匹配项、缺失项的评估结果
    """
    text_lower = answer_text.lower() if answer_text else ""
    matched = []
    missing = []

    for item in category["items"]:
        keywords = item.get("keywords", [])
        if not keywords:
            continue
        # 任一关键词命中即算该信息点被覆盖
        is_matched = any(kw.lower() in text_lower for kw in keywords)
        if is_matched:
            matched.append(item)
        else:
            missing.append(item)

    total = len(category["items"])
    coverage = len(matched) / total if total > 0 else 0.0

    return {
        "description": category["description"],
        "total": total,
        "matched": len(matched),
        "coverage": round(coverage, 2),
        "matched_items": [item["label"] for item in matched],
        "missing_items": [item["label"] for item in missing],
    }


def evaluate_scoring_sum(query_results: list) -> dict:
    """验证评分标准的分值总和是否为 100。"""
    scoring_answer = ""
    for q in query_results:
        if q.get("id") == "scoring":
            scoring_answer = q.get("answer", "")
            break

    if not scoring_answer:
        return {"check": "skipped", "reason": "未找到评分标准查询结果"}

    # 尝试从答案中提取数值
    import re
    numbers = re.findall(r'(\d+)\s*分', scoring_answer)
    values = [int(n) for n in numbers if int(n) <= 100]
    total = sum(values)

    return {
        "check": "computed" if values else "no_numbers",
        "extracted_scores": values,
        "sum": total,
        "expected_sum": 100,
        "is_correct": total == 100,
    }


def evaluate_table_structure(query_results: list) -> dict:
    """评估表格结构保留率。

    检查供货清单和技术参数表的查询结果中，是否保留了表格结构信息
    （如行列对应、数量、型号等）。
    """
    results = {}

    # 供货清单表格
    supply_answer = ""
    for q in query_results:
        if q.get("id") == "supply_list":
            supply_answer = q.get("answer", "")
            break

    supply_items = GROUND_TRUTH["supply_list"]["items"]
    supply_matched = sum(
        1 for item in supply_items
        if any(kw.lower() in supply_answer.lower() for kw in item["keywords"])
    )
    results["supply_list"] = {
        "total_items": len(supply_items),
        "matched_items": supply_matched,
        "retention": round(supply_matched / len(supply_items), 2),
    }

    # 技术参数表
    tech_keywords = ["380", "690", "97", "98.5", "IP20", "300"]
    tech_matched = sum(
        1 for kw in tech_keywords if kw.lower() in supply_answer.lower()
    )
    # 技术参数可能在 scoring 或其他查询中提到，合并所有答案检查
    all_answers = " ".join(q.get("answer", "") for q in query_results)
    tech_matched = sum(1 for kw in tech_keywords if kw.lower() in all_answers.lower())
    results["tech_params"] = {
        "total_items": len(tech_keywords),
        "matched_items": tech_matched,
        "retention": round(tech_matched / len(tech_keywords), 2),
    }

    return results


def evaluate_numeric_accuracy(query_results: list) -> dict:
    """评估关键数值的准确性。

    检查关键数值是否在解析结果中出现且正确。
    """
    all_answers = " ".join(q.get("answer", "") for q in query_results).lower()

    critical_numbers = [
        {"label": "注册资本 1000万", "value": "1000万", "category": "资质"},
        {"label": "业绩合同 200万", "value": "200万", "category": "业绩"},
        {"label": "营业收入 3000万", "value": "3000万", "category": "财务"},
        {"label": "资产负债率 70%", "value": "70%", "category": "财务"},
        {"label": "变频柜功率 55KW", "value": "55kw", "category": "供货"},
        {"label": "质保期 24个月", "value": "24个月", "category": "商务"},
        {"label": "预付款 30%", "value": "30%", "category": "商务"},
        {"label": "违约金 0.5%", "value": "0.5%", "category": "商务"},
    ]

    matched = []
    missing = []
    for num in critical_numbers:
        if num["value"].lower() in all_answers:
            matched.append(num)
        else:
            missing.append(num)

    return {
        "total": len(critical_numbers),
        "matched": len(matched),
        "accuracy": round(len(matched) / len(critical_numbers), 2),
        "matched_numbers": [n["label"] for n in matched],
        "missing_numbers": [n["label"] for n in missing],
    }


# ==================== 查询结果映射 ====================

def map_queries_to_categories(query_results: list) -> dict:
    """将查询结果映射到 Ground Truth 的类别。"""
    mapping = {
        "qualification": "qualification",
        "performance": "performance",
        "financial": "financial",
        "personnel": "personnel",
        "scoring": "scoring",
        "supply_list": "supply_list",
    }

    category_answers = {}
    for q in query_results:
        qid = q.get("id", "")
        if qid in mapping:
            category_answers[mapping[qid]] = q.get("answer", "")

    return category_answers


# ==================== 主流程 ====================

def print_checklist():
    """打印关键信息清单（不评估）。"""
    print("=" * 70)
    print("标书样本关键信息清单（Ground Truth）")
    print("=" * 70)

    total_items = 0
    for cat_key, cat in GROUND_TRUTH.items():
        count = len(cat["items"])
        total_items += count
        print(f"\n【{cat['description']}】({count} 项)")
        for item in cat["items"]:
            kws = " / ".join(item.get("keywords", []))
            print(f"  - {item['label']}  [关键词: {kws}]")

    print(f"\n{'=' * 70}")
    print(f"总计 {total_items} 个关键信息点")
    print(f"{'=' * 70}")


def evaluate(parse_results_path: str):
    """读取 parse_results.json 并执行评估。"""
    results_path = Path(parse_results_path)
    if not results_path.exists():
        print(f"[ERROR] 解析结果文件不存在: {results_path}")
        print(f"        请先运行 test_parse.py 生成 parse_results.json")
        sys.exit(1)

    with open(results_path, "r", encoding="utf-8") as f:
        parse_data = json.load(f)

    query_results = parse_data.get("query_results", [])
    if not query_results:
        print("[ERROR] 解析结果中没有查询数据")
        sys.exit(1)

    category_answers = map_queries_to_categories(query_results)

    print("=" * 70)
    print("RAG-Anything 解析效果评估报告")
    print("=" * 70)
    print(f"  评估文件: {results_path}")
    print(f"  验证时间: {parse_data.get('validation_time', '?')}")
    print(f"  文档类型: {parse_data.get('doc_type', '?')}")

    # ---- 1. 信息覆盖率评估 ----
    print(f"\n{'─' * 70}")
    print("1. 信息覆盖率评估（Coverage）")
    print(f"{'─' * 70}")

    coverage_results = {}
    eval_categories = ["qualification", "performance", "financial",
                       "personnel", "scoring", "supply_list"]

    for cat_key in eval_categories:
        cat = GROUND_TRUTH[cat_key]
        answer = category_answers.get(cat_key, "")
        result = evaluate_coverage(answer, cat)
        coverage_results[cat_key] = result

        status = "✅" if result["coverage"] >= 0.8 else ("⚠️" if result["coverage"] >= 0.5 else "❌")
        print(f"\n  {status} {cat['description']}")
        print(f"     覆盖率: {result['matched']}/{result['total']} ({result['coverage']:.0%})")
        if result["missing_items"]:
            print(f"     缺失: {', '.join(result['missing_items'])}")

    # 汇总覆盖率
    total_matched = sum(r["matched"] for r in coverage_results.values())
    total_items = sum(r["total"] for r in coverage_results.values())
    overall_coverage = total_matched / total_items if total_items > 0 else 0

    # ---- 2. 表格结构保留率 ----
    print(f"\n{'─' * 70}")
    print("2. 表格结构保留率（Table Retention）")
    print(f"{'─' * 70}")

    table_results = evaluate_table_structure(query_results)
    for table_name, tr in table_results.items():
        status = "✅" if tr["retention"] >= 0.8 else ("⚠️" if tr["retention"] >= 0.5 else "❌")
        print(f"  {status} {table_name}: {tr['matched_items']}/{tr['total_items']} ({tr['retention']:.0%})")

    # ---- 3. 数值准确性 ----
    print(f"\n{'─' * 70}")
    print("3. 数值准确性（Numeric Accuracy）")
    print(f"{'─' * 70}")

    numeric_result = evaluate_numeric_accuracy(query_results)
    status = "✅" if numeric_result["accuracy"] >= 0.8 else ("⚠️" if numeric_result["accuracy"] >= 0.5 else "❌")
    print(f"  {status} 准确率: {numeric_result['matched']}/{numeric_result['total']} ({numeric_result['accuracy']:.0%})")
    if numeric_result["missing_numbers"]:
        print(f"     缺失数值: {', '.join(numeric_result['missing_numbers'])}")

    # ---- 4. 评分标准总分校验 ----
    print(f"\n{'─' * 70}")
    print("4. 评分标准总分校验")
    print(f"{'─' * 70}")

    scoring_check = evaluate_scoring_sum(query_results)
    if scoring_check["check"] == "computed":
        status = "✅" if scoring_check["is_correct"] else "❌"
        print(f"  {status} 提取分值: {scoring_check['extracted_scores']}")
        print(f"     总分: {scoring_check['sum']}（期望 {scoring_check['expected_sum']}）")
    else:
        print(f"  ⚠️ {scoring_check.get('reason', '无法校验')}")

    # ---- 总体评估 ----
    print(f"\n{'=' * 70}")
    print("总体评估")
    print(f"{'=' * 70}")

    grades = []
    grades.append(("信息覆盖率", overall_coverage))
    grades.append(("表格保留率", sum(t["retention"] for t in table_results.values()) / len(table_results)))
    grades.append(("数值准确性", numeric_result["accuracy"]))

    print(f"  信息覆盖率:   {overall_coverage:.0%} ({total_matched}/{total_items})")
    print(f"  表格保留率:   {grades[1][1]:.0%}")
    print(f"  数值准确性:   {numeric_result['accuracy']:.0%}")

    avg_score = sum(g[1] for g in grades) / len(grades)
    print(f"\n  综合评分: {avg_score:.0%}")

    if avg_score >= 0.8:
        verdict = "✅ 优秀 — RAG-Anything 解析效果良好，可进入下一阶段开发"
    elif avg_score >= 0.6:
        verdict = "⚠️ 合格 — 基本可用，但部分信息解析不完整，需优化 prompt 或解析策略"
    else:
        verdict = "❌ 不达标 — 解析效果不佳，需检查 RAG-Anything 配置或更换模型"

    print(f"  评估结论: {verdict}")

    # 保存评估报告
    report = {
        "evaluation_time": parse_data.get("validation_time", ""),
        "doc_type": parse_data.get("doc_type", ""),
        "coverage": {
            "overall": round(overall_coverage, 2),
            "by_category": {k: {"coverage": v["coverage"], "matched": v["matched"],
                                "total": v["total"], "missing": v["missing_items"]}
                            for k, v in coverage_results.items()},
        },
        "table_retention": table_results,
        "numeric_accuracy": {
            "accuracy": numeric_result["accuracy"],
            "matched": numeric_result["matched"],
            "total": numeric_result["total"],
            "missing": numeric_result["missing_numbers"],
        },
        "scoring_sum_check": scoring_check,
        "overall_score": round(avg_score, 2),
        "verdict": verdict,
    }

    report_path = Path(results_path).parent / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  评估报告已保存: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="RAG-Anything 解析效果评估")
    parser.add_argument("--file", default="parse_results.json", help="解析结果 JSON 文件路径")
    parser.add_argument("--checklist", action="store_true", help="只打印关键信息清单，不评估")
    args = parser.parse_args()

    if args.checklist:
        print_checklist()
        return

    # 解析文件路径
    file_path = args.file
    if not Path(file_path).is_absolute():
        file_path = str(Path(__file__).parent / file_path)

    evaluate(file_path)


if __name__ == "__main__":
    main()
