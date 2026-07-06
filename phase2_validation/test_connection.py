#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG-Tender Assistant Phase 2 — API 连通性测试脚本

测试三项：
  1. DeepSeek LLM 连通性（发一个简单 prompt）
  2. 硅基流动 Embedding 连通性（向量化一句话）
  3. 硅基流动 Nex-N2-Pro 视觉能力（发一张图片，看是否支持 image_url 格式）

三个测试独立运行，输出明确的 PASS / FAIL + 错误信息。

使用方法：
  1. 编辑同目录下 config.yaml，填入真实 API Key
  2. 运行：python test_connection.py
  3. 也可只跑单项测试：python test_connection.py --only llm|embedding|vision
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
    """读取同目录下的 config.yaml。"""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print(f"[ERROR] 配置文件不存在: {config_path}")
        sys.exit(1)

    if yaml is None:
        # yaml 未安装时的简易降级解析（仅支持本配置用到的结构）
        print("[WARN] PyYAML 未安装，尝试用 pip install pyyaml 安装后重试。")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_key(api_key: str, name: str) -> bool:
    """检查 Key 是否仍是占位符。"""
    if api_key.startswith("YOUR_") or not api_key:
        print(f"  [{name}] ❌ FAIL — API Key 仍是占位符或为空，请编辑 config.yaml 填入真实 Key")
        return False
    return True


# ==================== 通用 HTTP 请求工具 ====================

def _post_json(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    """发送 POST JSON 请求，返回解析后的 JSON 或抛出异常。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


# ==================== 测试 1：DeepSeek LLM ====================

def test_llm(cfg: dict) -> bool:
    """测试 DeepSeek LLM 连通性。"""
    print("\n" + "=" * 60)
    print("测试 1/3：DeepSeek LLM 连通性")
    print("=" * 60)

    llm = cfg.get("llm", {})
    api_key = llm.get("api_key", "")
    if not _check_key(api_key, "LLM"):
        return False

    base_url = llm.get("base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = llm.get("model", "deepseek-chat")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个简洁的助手。"},
            {"role": "user", "content": "请用一句话回答：1+1等于几？"},
        ],
        "max_tokens": 64,
        "temperature": 0.1,
    }

    print(f"  请求地址: {url}")
    print(f"  模型: {model}")
    print(f"  Prompt: 请用一句话回答：1+1等于几？")

    start = time.time()
    try:
        result = _post_json(url, headers, payload, timeout=60)
        elapsed = time.time() - start
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  回复: {content.strip()}")
        print(f"  Token 用量: prompt={usage.get('prompt_tokens', '?')}, "
              f"completion={usage.get('completion_tokens', '?')}, "
              f"total={usage.get('total_tokens', '?')}")
        print("  [LLM] ✅ PASS — DeepSeek LLM 连通正常")
        return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP 错误 {e.code}: {err_body[:500]}")
        print("  [LLM] ❌ FAIL")
        return False
    except Exception as e:
        print(f"  异常: {type(e).__name__}: {e}")
        print("  [LLM] ❌ FAIL")
        return False


# ==================== 测试 2：硅基流动 Embedding ====================

def test_embedding(cfg: dict) -> bool:
    """测试硅基流动 BGE-M3 Embedding 连通性。"""
    print("\n" + "=" * 60)
    print("测试 2/3：硅基流动 Embedding 连通性（BGE-M3）")
    print("=" * 60)

    emb = cfg.get("embedding", {})
    api_key = emb.get("api_key", "")
    if not _check_key(api_key, "Embedding"):
        return False

    base_url = emb.get("base_url", "https://api.siliconflow.cn/v1").rstrip("/")
    model = emb.get("model", "BAAI/bge-m3")
    expected_dim = emb.get("dimension", 1024)
    url = f"{base_url}/embeddings"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": "控制柜配电柜变频柜采购招标公告",
    }

    print(f"  请求地址: {url}")
    print(f"  模型: {model}")
    print(f"  输入文本: {payload['input']}")

    start = time.time()
    try:
        result = _post_json(url, headers, payload, timeout=30)
        elapsed = time.time() - start
        data_list = result.get("data", [])
        if not data_list:
            print(f"  返回数据为空: {result}")
            print("  [Embedding] ❌ FAIL")
            return False
        vector = data_list[0].get("embedding", [])
        actual_dim = len(vector)
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  向量维度: {actual_dim}（期望 {expected_dim}）")
        print(f"  向量前 5 维: {[round(v, 4) for v in vector[:5]]}")
        if actual_dim != expected_dim:
            print(f"  ⚠️ 维度不匹配：实际 {actual_dim} vs 期望 {expected_dim}")
            print("  [Embedding] ⚠️ WARN — 维度不一致，但仍可连通")
            return True
        print("  [Embedding] ✅ PASS — BGE-M3 Embedding 连通正常，维度匹配")
        return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP 错误 {e.code}: {err_body[:500]}")
        print("  [Embedding] ❌ FAIL")
        return False
    except Exception as e:
        print(f"  异常: {type(e).__name__}: {e}")
        print("  [Embedding] ❌ FAIL")
        return False


# ==================== 测试 3：Nex-N2-Pro 视觉能力（关键）====================

def _generate_test_image_base64() -> str:
    """生成一张包含中文文字的简单测试图片（PNG），返回 base64 编码字符串。

    不依赖第三方库，用纯 Python 生成一张纯色背景 + 文字的图片。
    优先尝试用 Pillow 生成高质量图片；若 Pillow 不可用，则用预置的
    最小化 PNG（1x1 像素）做连通性测试（主要验证 API 是否接受 image_url 格式）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (480, 160), color=(30, 60, 120))
        draw = ImageDraw.Draw(img)
        text = "标书测试图片 RAG-Anything"
        # 尝试加载系统字体
        font = None
        for font_path in [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]:
            try:
                font = ImageFont.truetype(font_path, 28)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        draw.text((20, 60), text, fill=(255, 255, 255), font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # Pillow 不可用，返回一张预制的最小有效 PNG（8x8 蓝色块）
        # 这足以验证 API 是否接受 image_url 输入格式
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVQI12P8"
            "z8BQz0AEYBxVSF+FAP5FAAA+T+l2wAAAABJRU5ErkJggg=="
        )


def test_vision(cfg: dict) -> bool:
    """测试硅基流动 Nex-N2-Pro 是否支持 OpenAI Vision API 的 image_url 格式。

    这是本项目的关键技术验证点：
      - 如果返回正常识别 → ✅ Nex-N2-Pro 可作 Vision 模型
      - 如果报错（如 image_url not supported / invalid content format）
        → ❌ 不支持，需切换到智谱 GLM-4V
    """
    print("\n" + "=" * 60)
    print("测试 3/3：Nex-N2-Pro 视觉能力（image_url 格式）★ 关键")
    print("=" * 60)

    vis = cfg.get("vision", {})
    api_key = vis.get("api_key", "")
    if not _check_key(api_key, "Vision"):
        return False

    base_url = vis.get("base_url", "https://api.siliconflow.cn/v1").rstrip("/")
    model = vis.get("model", "nex-agi/Nex-N2-Pro")
    url = f"{base_url}/chat/completions"

    img_b64 = _generate_test_image_base64()
    print(f"  请求地址: {url}")
    print(f"  模型: {model}")
    print(f"  图片格式: data:image/png;base64,（长度 {len(img_b64)} 字符）")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图片里有什么文字？请描述图片内容。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 256,
        "temperature": 0.1,
    }

    start = time.time()
    try:
        result = _post_json(url, headers, payload, timeout=90)
        elapsed = time.time() - start
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  回复: {content.strip()[:500]}")
        if usage:
            print(f"  Token 用量: {usage}")
        print("  [Vision] ✅ PASS — Nex-N2-Pro 支持 image_url 格式，可用作 Vision 模型！")
        return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP 错误 {e.code}: {err_body[:800]}")
        # 判断是否为格式不支持
        lower_err = err_body.lower()
        if any(kw in lower_err for kw in [
            "image_url", "image", "not support", "invalid", "content format",
            "multimodal", "vision",
        ]):
            print("  [Vision] ❌ FAIL — Nex-N2-Pro 很可能不支持 image_url 多模态输入格式")
            print("           👉 建议切换到备选模型：智谱 GLM-4V 或 OpenAI gpt-4o")
        else:
            print(f"  [Vision] ❌ FAIL — HTTP {e.code}，可能是 Key/额度/模型名问题")
        return False
    except Exception as e:
        print(f"  异常: {type(e).__name__}: {e}")
        print("  [Vision] ❌ FAIL")
        return False


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="RAG-Tender Phase 2 API 连通性测试")
    parser.add_argument(
        "--only",
        choices=["llm", "embedding", "vision"],
        help="只运行指定测试",
    )
    args = parser.parse_args()

    cfg = load_config()
    results = {}

    if args.only is None or args.only == "llm":
        results["llm"] = test_llm(cfg)
    if args.only is None or args.only == "embedding":
        results["embedding"] = test_embedding(cfg)
    if args.only is None or args.only == "vision":
        results["vision"] = test_vision(cfg)

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {name:12s} {status}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  通过: {passed}/{total}")

    if passed == total:
        print("\n  🎉 全部通过！可以继续运行 test_parse.py 进行标书解析验证。")
        return 0
    else:
        print("\n  ⚠️ 部分测试未通过，请检查 API Key 和网络后重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
