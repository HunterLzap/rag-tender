#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG-Tender Assistant Phase 2 — Vision API 专项验证脚本

专门测试 Nex-N2-Pro 是否支持 OpenAI Vision API 的 image_url 输入格式。
这是项目能否用 RAG-Anything 做多模态解析的关键技术验证点。

测试矩阵：
  测试 A：用生成的文字图片测试基本 image_url 支持
  测试 B：用标书 PDF 某页截图测试复杂图像识别能力
  测试 C：测试 base64 内联 vs http URL 两种图片传入方式（如有公网图床）
  测试 D：测试 fallback 模型（智谱 GLM-4V）作为对照

判定逻辑：
  - 测试 A 通过 → Nex-N2-Pro 支持 image_url → ✅ 可用
  - 测试 A 失败但报错含 image/invalid/content → ❌ 不支持，需切换 GLM-4V
  - 测试 A 失败且报错为鉴权/额度 → 无法判定，需检查 Key

使用方法：
  1. 编辑 config.yaml 填入真实 API Key
  2. 运行：python test_vision_capability.py
  3. 可指定模型：python test_vision_capability.py --model nex-agi/Nex-N2-Pro
"""

import argparse
import base64
import io
import json
import sys
import time
import urllib.request
import urllib.error
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


# ==================== HTTP 工具 ====================

def post_json(url: str, api_key: str, payload: dict, timeout: int = 90) -> dict:
    """发送 POST JSON 请求并返回解析结果，失败时抛出 HTTPError 或 Exception。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ==================== 图片生成工具 ====================

def generate_text_image_b64() -> str:
    """生成一张包含中文文字的测试图片，返回 base64 编码。

    优先使用 Pillow 生成清晰图片；不可用时回退到预置最小 PNG。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        width, height = 600, 200
        img = Image.new("RGB", (width, height), color=(25, 50, 110))
        draw = ImageDraw.Draw(img)

        lines = [
            "RAG-Tender 标书解析测试",
            "控制柜 配电柜 变频柜",
            "招标编号：YB2024-01-RTA",
        ]
        font = None
        for font_path in [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]:
            try:
                font = ImageFont.truetype(font_path, 24)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        y = 30
        for line in lines:
            draw.text((30, y), line, fill=(255, 255, 255), font=font)
            y += 50

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        print(f"  [图片生成] 使用 Pillow 生成图片，大小 {len(buf.getvalue())} bytes")
        return b64
    except ImportError:
        b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVQI12P8"
            "z8BQz0AEYBxVSF+FAP5FAAA+T+l2wAAAABJRU5ErkJggg=="
        )
        print("  [图片生成] Pillow 不可用，使用预置最小 PNG（仅测试 API 格式接受度）")
        return b64


def pdf_page_to_image_b64(pdf_path: str, page_num: int = 1) -> str:
    """将 PDF 指定页渲染为图片并返回 base64。

    优先使用 PyMuPDF (fitz)；不可用则返回空字符串跳过该测试。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(f"  [PDF转图] PyMuPDF 未安装，跳过 PDF 截图测试")
        print(f"            如需安装：pip install PyMuPDF")
        return ""

    if not Path(pdf_path).exists():
        print(f"  [PDF转图] PDF 文件不存在: {pdf_path}")
        return ""

    try:
        doc = fitz.open(pdf_path)
        if page_num > len(doc):
            page_num = 1
        page = doc[page_num - 1]
        # 2x 缩放以获得更清晰的图像
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("ascii")
        doc.close()
        print(f"  [PDF转图] 成功渲染 PDF 第 {page_num} 页，图片大小 {len(img_bytes)} bytes")
        return b64
    except Exception as e:
        print(f"  [PDF转图] 失败: {type(e).__name__}: {e}")
        return ""


# ==================== Vision 测试核心 ====================

class VisionTestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error_msg = ""
        self.response = ""
        self.elapsed = 0.0
        self.error_type = ""  # "format_unsupported" | "auth" | "timeout" | "other"


def run_vision_test(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    image_b64: str,
    prompt: str,
    image_mime: str = "image/png",
) -> VisionTestResult:
    """执行一次 Vision API 调用测试。"""
    result = VisionTestResult(name)
    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 512,
        "temperature": 0.1,
    }

    print(f"\n  --- {name} ---")
    print(f"  模型: {model}")
    print(f"  Prompt: {prompt}")
    print(f"  图片: data:{image_mime};base64,...（长度 {len(image_b64)} 字符）")

    start = time.time()
    try:
        resp = post_json(url, api_key, payload, timeout=90)
        result.elapsed = time.time() - start
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        result.response = content.strip()
        result.passed = True
        print(f"  耗时: {result.elapsed:.2f}s")
        print(f"  回复: {result.response[:400]}")
        print(f"  ✅ PASS")
    except urllib.error.HTTPError as e:
        result.elapsed = time.time() - start
        err_body = e.read().decode("utf-8", errors="replace")
        result.error_msg = err_body[:800]
        lower = err_body.lower()
        if any(kw in lower for kw in [
            "image_url", "not support", "invalid content", "content format",
            "multimodal", "unsupported", "image",
        ]):
            result.error_type = "format_unsupported"
        elif e.code in (401, 403):
            result.error_type = "auth"
        else:
            result.error_type = "other"
        print(f"  耗时: {result.elapsed:.2f}s")
        print(f"  HTTP 错误 {e.code}: {err_body[:500]}")
        print(f"  ❌ FAIL（类型: {result.error_type}）")
    except Exception as e:
        result.elapsed = time.time() - start
        result.error_msg = f"{type(e).__name__}: {e}"
        result.error_type = "other"
        print(f"  异常: {result.error_msg}")
        print(f"  ❌ FAIL")

    return result


# ==================== 主测试流程 ====================

def main():
    parser = argparse.ArgumentParser(description="Vision API 专项验证")
    parser.add_argument("--model", default=None, help="覆盖 config.yaml 中的 vision 模型名")
    parser.add_argument("--skip-pdf", action="store_true", help="跳过 PDF 截图测试")
    args = parser.parse_args()

    cfg = load_config()
    vis = cfg.get("vision", {})
    api_key = vis.get("api_key", "")

    if api_key.startswith("YOUR_") or not api_key:
        print("[ERROR] Vision API Key 仍是占位符，请编辑 config.yaml 填入真实 Key")
        sys.exit(1)

    base_url = vis.get("base_url", "https://api.siliconflow.cn/v1")
    model = args.model or vis.get("model", "nex-agi/Nex-N2-Pro")
    fallback_model = vis.get("fallback_model", "glm-4v")

    print("=" * 70)
    print("RAG-Tender Assistant — Vision API 专项验证")
    print("=" * 70)
    print(f"  API 地址: {base_url}")
    print(f"  主测模型: {model}")
    print(f"  备选模型: {fallback_model}")

    all_results = []

    # ---- 测试 A：生成文字图片，测基本 image_url 支持 ----
    print("\n" + "#" * 50)
    print("# 测试 A：基本 image_url 支持（生成的文字图片）")
    print("#" * 50)
    img_a = generate_text_image_b64()
    if img_a:
        r = run_vision_test(
            "A-基本图片识别",
            base_url, api_key, model, img_a,
            "这张图片里有什么文字？请逐字列出。",
        )
        all_results.append(r)

    # ---- 测试 B：PDF 某页截图，测复杂图像 ----
    print("\n" + "#" * 50)
    print("# 测试 B：标书 PDF 截图识别（复杂图像）")
    print("#" * 50)
    if not args.skip_pdf:
        pdf_path = str(Path(__file__).parent / cfg.get("documents", {}).get("pdf_path", "../samples/控制柜配电柜变频柜采购招标公告_样本.pdf"))
        img_b = pdf_page_to_image_b64(pdf_path, page_num=1)
        if img_b:
            r = run_vision_test(
                "B-PDF截图识别",
                base_url, api_key, model, img_b,
                "这是一页标书文档的截图。请识别其中的标题和主要章节名称。",
            )
            all_results.append(r)
    else:
        print("  已跳过（--skip-pdf）")

    # ---- 测试 C：如果主模型失败，测试 fallback 模型 ----
    primary_failed = any(not r.passed and r.error_type == "format_unsupported" for r in all_results)
    if primary_failed:
        print("\n" + "#" * 50)
        print(f"# 测试 C：主模型不支持，测试备选模型 {fallback_model}")
        print("#" * 50)
        img_c = generate_text_image_b64()
        if img_c:
            r = run_vision_test(
                f"C-备选模型({fallback_model})",
                base_url, api_key, fallback_model, img_c,
                "这张图片里有什么文字？请逐字列出。",
            )
            all_results.append(r)

    # ==================== 汇总报告 ====================
    print("\n" + "=" * 70)
    print("Vision API 验证汇总报告")
    print("=" * 70)

    for r in all_results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"  {r.name:30s} {status}  ({r.elapsed:.1f}s)")
        if not r.passed:
            print(f"    错误类型: {r.error_type}")
            print(f"    错误信息: {r.error_msg[:200]}")

    # ---- 关键结论 ----
    print("\n" + "-" * 70)
    print("关键结论：")
    print("-" * 70)

    primary_results = [r for r in all_results if "A-" in r.name or "B-" in r.name]
    any_primary_pass = any(r.passed for r in primary_results)
    any_format_unsupported = any(r.error_type == "format_unsupported" for r in primary_results)

    if any_primary_pass:
        print(f"  ✅ 模型 [{model}] 支持 image_url 多模态输入格式！")
        print(f"     可作为 RAG-Anything 的 Vision 模型使用。")
        print(f"     下一步：运行 test_parse.py 进行标书解析验证。")
        verdict = "SUPPORTED"
    elif any_format_unsupported:
        print(f"  ❌ 模型 [{model}] 不支持 image_url 多模态输入格式！")
        print(f"     建议切换到备选模型：{fallback_model}")
        # 检查 fallback 是否通过
        fallback_results = [r for r in all_results if "C-" in r.name]
        if fallback_results and fallback_results[0].passed:
            print(f"  ✅ 备选模型 [{fallback_model}] 测试通过，推荐使用！")
            verdict = "FALLBACK_OK"
        else:
            print(f"  ⚠️ 备选模型 [{fallback_model}] 也未通过，请检查 Key 或换其他模型。")
            verdict = "ALL_FAILED"
    else:
        print(f"  ⚠️ 模型 [{model}] 测试失败，但非格式问题（可能是 Key/额度/网络）。")
        print(f"     请检查 API Key 和账户余额后重试。")
        verdict = "INCONCLUSIVE"

    # 写结论到文件
    report_path = Path(__file__).parent / "vision_test_report.json"
    report = {
        "model": model,
        "fallback_model": fallback_model,
        "verdict": verdict,
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "elapsed": round(r.elapsed, 2),
                "error_type": r.error_type,
                "error_msg": r.error_msg[:500],
                "response": r.response[:500],
            }
            for r in all_results
        ],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告已保存: {report_path}")

    return 0 if verdict in ("SUPPORTED", "FALLBACK_OK") else 1


if __name__ == "__main__":
    sys.exit(main())
