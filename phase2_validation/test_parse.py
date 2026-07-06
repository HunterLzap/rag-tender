#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG-Tender Assistant Phase 2 — RAG-Anything 标书解析验证脚本

使用 RAG-Anything 对标书样本 PDF 进行解析：
  1. 初始化 RAGAnything（使用 config.yaml 的 API 配置）
  2. 用 process_document_complete() 处理标书样本 PDF
  3. 用 aquery() 查询关键信息：
     - "投标人的资质要求有哪些？"
     - "评分标准是什么？"
     - "供货清单有哪些设备？"
  4. 输出解析结果到 JSON 文件

前置条件：
  - raganything 已安装：pip install 'raganything[all]'
  - config.yaml 已填入真实 API Key
  - test_connection.py 全部通过

使用方法：
  python test_parse.py
  python test_parse.py --doc pdf      # 用 PDF 解析（多模态）
  python test_parse.py --doc markdown # 用 Markdown 解析（纯文本）
"""

import argparse
import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ==================== 配置加载 ====================

def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print(f"[ERROR] 配置文件不存在: {config_path}")
        sys.exit(1)
    if yaml is None:
        print("[ERROR] PyYAML 未安装，请运行: pip install pyyaml")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_doc_path(cfg: dict, doc_type: str) -> str:
    """根据 doc_type 解析文档路径。"""
    docs = cfg.get("documents", {})
    if doc_type == "pdf":
        rel = docs.get("pdf_path", "../samples/控制柜配电柜变频柜采购招标公告_样本.pdf")
    else:
        rel = docs.get("markdown_path", "../samples/控制柜配电柜变频柜采购招标公告_样本.md")
    full = (Path(__file__).parent / rel).resolve()
    return str(full)


# ==================== RAG-Anything 初始化 ====================

def init_raganything(cfg: dict):
    """初始化 RAGAnything 实例。

    RAG-Anything 1.3.x 构造函数签名：
      RAGAnything(llm_model_func, vision_model_func, embedding_func, config, lightrag_kwargs)

    LLM/Embedding 函数位于 lightrag.llm.openai 模块（非 lightrag.llm）。
    """
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed, wrap_embedding_func_with_attrs
    from raganything import RAGAnything
    from raganything.config import RAGAnythingConfig

    llm_cfg = cfg.get("llm", {})
    emb_cfg = cfg.get("embedding", {})
    vis_cfg = cfg.get("vision", {})
    ra_cfg = cfg.get("raganything", {})

    # ---- LLM 模型函数（DeepSeek）----
    async def llm_model_func(
        prompt,
        system_prompt=None,
        history_messages=None,
        keyword_extraction=False,
        **kwargs,
    ) -> str:
        resp = await openai_complete_if_cache(
            llm_cfg.get("model", "deepseek-chat"),
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
            api_key=llm_cfg.get("api_key", ""),
            keyword_extraction=keyword_extraction,
            **kwargs,
        )
        return resp

    # ---- Embedding 模型函数（硅基流动 BGE-M3）----
    # wrap_embedding_func_with_attrs 是装饰器，需在函数定义时使用，
    # 它会创建 EmbeddingFunc 实例并自动注入 embedding_dim 参数。
    embedding_dim = emb_cfg.get("dimension", 1024)

    @wrap_embedding_func_with_attrs(embedding_dim=embedding_dim, max_token_size=8192)
    async def embedding_func(texts: list, embedding_dim: int = None) -> list:
        resp = await openai_embed(
            texts,
            model=emb_cfg.get("model", "BAAI/bge-m3"),
            base_url=emb_cfg.get("base_url", "https://api.siliconflow.cn/v1"),
            api_key=emb_cfg.get("api_key", ""),
        )
        return resp

    # ---- Vision 模型函数（硅基流动 Nex-N2-Pro）----
    # RAG-Anything 的 vision_model_func 签名：
    #   async def vision_model_func(prompt, image_base64_list, system_prompt=None, **kwargs) -> str
    async def vision_model_func(
        prompt: str,
        image_base64_list: list,
        system_prompt=None,
        **kwargs,
    ) -> str:
        """Vision 模型调用，使用 OpenAI 兼容的 image_url 格式。"""
        import urllib.request
        import urllib.error

        vis_base = vis_cfg.get("base_url", "").rstrip("/")
        url = f"{vis_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {vis_cfg.get('api_key', '')}",
            "Content-Type": "application/json",
        }

        content = [{"type": "text", "text": prompt}]
        for img_b64 in image_base64_list:
            if isinstance(img_b64, str) and img_b64.startswith("data:"):
                url_str = img_b64
            else:
                url_str = f"data:image/png;base64,{img_b64}"
            content.append({
                "type": "image_url",
                "image_url": {"url": url_str},
            })

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        payload = {
            "model": vis_cfg.get("model", "nex-agi/Nex-N2-Pro"),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.1),
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")

    # ---- 构造 RAGAnythingConfig ----
    workspace = str((Path(__file__).parent / ra_cfg.get("workspace_dir", "./rag_workspace")).resolve())
    Path(workspace).mkdir(parents=True, exist_ok=True)

    ra_config = RAGAnythingConfig(
        working_dir=workspace,
        parser=ra_cfg.get("parser", "mineru"),
        enable_image_processing=ra_cfg.get("enable_image_processing", True),
        enable_table_processing=ra_cfg.get("enable_table_processing", True),
    )

    # ---- 初始化 RAGAnything ----
    print(f"  工作目录: {workspace}")
    print(f"  LLM: {llm_cfg.get('model')} @ {llm_cfg.get('base_url')}")
    print(f"  Embedding: {emb_cfg.get('model')} (dim={embedding_dim}) @ {emb_cfg.get('base_url')}")
    print(f"  Vision: {vis_cfg.get('model')} @ {vis_cfg.get('base_url')}")

    try:
        rag = RAGAnything(
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            vision_model_func=vision_model_func,
            config=ra_config,
        )
        print("  [RAGAnything] 初始化成功")
    except Exception as e:
        print(f"  [RAGAnything] 初始化失败（带 Vision）: {type(e).__name__}: {e}")
        print("  尝试不带 Vision 降级初始化 ...")
        try:
            rag = RAGAnything(
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                config=ra_config,
            )
            print("  [RAGAnything] 降级初始化成功（无 Vision）")
            print("  ⚠️ 注意：未传入 vision_model_func，表格/图片解析可能受限")
        except Exception as e2:
            print(f"  [ERROR] RAGAnything 初始化完全失败: {type(e2).__name__}: {e2}")
            sys.exit(1)

    return rag


# ==================== 文档解析 ====================

async def process_document(rag, doc_path: str) -> dict:
    """用 RAG-Anything 处理文档，返回处理统计信息。"""
    print(f"\n{'=' * 60}")
    print(f"开始解析文档: {doc_path}")
    print(f"{'=' * 60}")

    if not Path(doc_path).exists():
        print(f"[ERROR] 文件不存在: {doc_path}")
        return {"success": False, "error": f"文件不存在: {doc_path}"}

    start = time.time()
    stats = {"doc_path": doc_path, "start_time": time.strftime("%Y-%m-%d %H:%M:%S")}

    # 尝试多种方法名以兼容不同版本
    process_methods = ["process_document_complete", "ainsert", "insert", "process_document"]
    processed = False
    for method_name in process_methods:
        method = getattr(rag, method_name, None)
        if method is None:
            continue
        try:
            print(f"  调用 rag.{method_name}() ...")
            result = method(doc_path)
            if asyncio.iscoroutine(result):
                result = await result
            stats["process_method"] = method_name
            processed = True
            print(f"  ✅ {method_name}() 调用成功")
            break
        except Exception as e:
            print(f"  ⚠️ {method_name}() 失败: {type(e).__name__}: {e}")
            stats.setdefault("method_errors", []).append(f"{method_name}: {e}")

    if not processed:
        stats["success"] = False
        stats["error"] = "所有处理方法均失败"
        stats["elapsed"] = round(time.time() - start, 2)
        return stats

    stats["success"] = True
    stats["elapsed"] = round(time.time() - start, 2)
    print(f"  解析耗时: {stats['elapsed']}s")
    return stats


# ==================== 查询验证 ====================

# 预设查询列表（对标书关键信息的验证）
QUERIES = [
    {
        "id": "qualification",
        "question": "投标人的资质要求有哪些？请逐条列出。",
        "expect_keywords": ["营业执照", "ISO9001", "ISO14001", "ISO45001", "CCC", "3C", "注册资本", "1000万"],
        "description": "资质要求（期望 7 项）",
    },
    {
        "id": "performance",
        "question": "投标人的业绩要求是什么？",
        "expect_keywords": ["3个", "200万", "合同", "中标通知书", "近三年"],
        "description": "业绩要求（期望 3 项）",
    },
    {
        "id": "financial",
        "question": "投标人的财务要求有哪些？",
        "expect_keywords": ["审计报告", "3000万", "资产负债率", "70%", "银行资信"],
        "description": "财务要求（期望 5 项）",
    },
    {
        "id": "personnel",
        "question": "投标人的项目团队人员要求是什么？",
        "expect_keywords": ["一级建造师", "高级工程师", "注册质量工程师", "注册安全工程师", "社保"],
        "description": "人员要求（期望 5 项）",
    },
    {
        "id": "scoring",
        "question": "评分标准是什么？各评分项的分值是多少？",
        "expect_keywords": ["投标报价", "30", "技术方案", "25", "设备性能", "20", "企业资质", "10", "项目团队", "10", "售后服务", "5"],
        "description": "评分标准（期望 6 项，总分 100）",
    },
    {
        "id": "supply_list",
        "question": "供货清单有哪些设备？请列出设备名称、型号、数量。",
        "expect_keywords": ["自动化控制柜", "变频柜", "PLC", "配电柜", "控制柜附件"],
        "description": "供货清单（期望 5 项）",
    },
]


async def run_queries(rag) -> list:
    """对预设查询逐一执行 aquery，返回结果列表。"""
    print(f"\n{'=' * 60}")
    print("开始查询验证")
    print(f"{'=' * 60}")

    results = []
    query_methods = ["aquery", "query"]

    for q in QUERIES:
        print(f"\n  [{q['id']}] {q['description']}")
        print(f"  问题: {q['question']}")

        answer = None
        for method_name in query_methods:
            method = getattr(rag, method_name, None)
            if method is None:
                continue
            try:
                start = time.time()
                result = method(q["question"])
                if asyncio.iscoroutine(result):
                    result = await result
                elapsed = round(time.time() - start, 2)
                # 结果可能是字符串或对象
                if isinstance(result, str):
                    answer = result
                elif isinstance(result, dict):
                    answer = result.get("response", result.get("answer", json.dumps(result, ensure_ascii=False)))
                else:
                    answer = str(result)
                print(f"  耗时: {elapsed}s")
                print(f"  回复: {answer[:300]}...")
                break
            except Exception as e:
                print(f"  ⚠️ {method_name}() 失败: {type(e).__name__}: {e}")

        if answer is None:
            answer = "[查询失败：所有方法均不可用]"

        # 关键词覆盖率检查
        answer_lower = answer.lower() if answer else ""
        matched = [kw for kw in q["expect_keywords"] if kw.lower() in answer_lower]
        coverage = len(matched) / len(q["expect_keywords"]) if q["expect_keywords"] else 0

        results.append({
            "id": q["id"],
            "description": q["description"],
            "question": q["question"],
            "answer": answer,
            "expect_keywords": q["expect_keywords"],
            "matched_keywords": matched,
            "coverage": round(coverage, 2),
        })
        print(f"  关键词覆盖: {len(matched)}/{len(q['expect_keywords'])} ({coverage:.0%})")
        missing = [kw for kw in q["expect_keywords"] if kw.lower() not in answer_lower]
        if missing:
            print(f"  未匹配: {missing}")

    return results


# ==================== 主流程 ====================

async def run(doc_type: str):
    cfg = load_config()

    print("=" * 60)
    print("RAG-Tender Assistant Phase 2 — RAG-Anything 解析验证")
    print("=" * 60)

    # 检查 Key
    llm_key = cfg.get("llm", {}).get("api_key", "")
    if llm_key.startswith("YOUR_"):
        print("[ERROR] API Key 仍是占位符，请编辑 config.yaml 填入真实 Key")
        sys.exit(1)

    # 初始化 RAGAnything
    print("\n[1/3] 初始化 RAGAnything ...")
    rag = init_raganything(cfg)

    # 解析文档
    doc_path = resolve_doc_path(cfg, doc_type)
    print(f"\n[2/3] 解析文档 ({doc_type}) ...")
    process_stats = await process_document(rag, doc_path)

    # 查询验证
    print(f"\n[3/3] 执行查询验证 ...")
    query_results = await run_queries(rag)

    # 汇总输出
    output = {
        "validation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "doc_type": doc_type,
        "doc_path": doc_path,
        "process_stats": process_stats,
        "query_results": query_results,
        "summary": {
            "total_queries": len(query_results),
            "avg_coverage": round(
                sum(q["coverage"] for q in query_results) / max(len(query_results), 1), 2
            ),
            "queries_above_80pct": sum(1 for q in query_results if q["coverage"] >= 0.8),
        },
    }

    output_path = Path(__file__).parent / "parse_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("验证完成！结果摘要：")
    print(f"{'=' * 60}")
    print(f"  文档解析: {'✅ 成功' if process_stats.get('success') else '❌ 失败'}")
    print(f"  解析耗时: {process_stats.get('elapsed', '?')}s")
    print(f"  查询总数: {output['summary']['total_queries']}")
    print(f"  平均覆盖率: {output['summary']['avg_coverage']:.0%}")
    print(f"  覆盖率≥80%的查询: {output['summary']['queries_above_80pct']}")
    print(f"\n  详细结果已保存: {output_path}")
    print(f"  可运行 evaluate_parse.py 对照评估解析效果")


def main():
    parser = argparse.ArgumentParser(description="RAG-Anything 标书解析验证")
    parser.add_argument(
        "--doc",
        choices=["pdf", "markdown"],
        default="pdf",
        help="解析文档类型（默认 pdf，测多模态）",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.doc))
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] 运行失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
