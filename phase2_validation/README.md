# RAG-Tender Assistant — Phase 2 技术验证

验证 RAG-Anything 对标书文档的解析能力，这是项目能否成立的关键技术验证。

## 目录结构

```
phase2_validation/
├── config.yaml                 # API 配置文件（需填入真实 Key）
├── test_connection.py          # API 连通性测试（LLM / Embedding / Vision）
├── test_vision_capability.py   # Vision API 专项验证（★ 关键）
├── test_parse.py               # RAG-Anything 标书解析验证
├── evaluate_parse.py           # 解析效果评估（静态对照）
├── README.md                   # 本文件
├── vision_test_report.json     # Vision 测试报告（运行后生成）
├── parse_results.json          # 解析结果（运行后生成）
└── evaluation_report.json      # 评估报告（运行后生成）
```

## 前置条件

| 依赖 | 说明 |
|------|------|
| Python 3.13+ | 推荐 3.13.12 |
| raganything | `pip install 'raganything[all]'`（1.3.1） |
| PyYAML | `pip install pyyaml`（读取 config.yaml） |
| Pillow | `pip install Pillow`（生成测试图片，可选） |
| PyMuPDF | `pip install PyMuPDF`（PDF 截图，可选） |

**推荐一次性安装依赖：**
```bash
# 在项目根目录
pip install pyyaml Pillow PyMuPDF
```

> 💡 **接手者注意**：本目录的脚本仅用于 Phase 2 技术验证。**主程序不依赖本目录**，主程序在 `backend/` 目录。本目录保留供验证 Vision API 等场景使用。

## 快速开始

### 第 1 步：填入 API Key

编辑 `config.yaml`，把以下占位符替换为真实 Key：

```yaml
llm:
  api_key: "YOUR_DEEPSEEK_KEY"      # ← 替换为 DeepSeek API Key
embedding:
  api_key: "YOUR_SILICONFLOW_KEY"   # ← 替换为硅基流动 API Key
vision:
  api_key: "YOUR_SILICONFLOW_KEY"   # ← 替换为硅基流动 API Key（同一 Key）
```

> - DeepSeek Key 获取：https://platform.deepseek.com/
> - 硅基流动 Key 获取：https://cloud.siliconflow.cn/

### 第 2 步：测试 API 连通性

```bash
# 在 phase2_validation 目录下
python test_connection.py
```

**预期输出：**
```
测试 1/3：DeepSeek LLM 连通性
  [LLM] ✅ PASS

测试 2/3：硅基流动 Embedding 连通性（BGE-M3）
  [Embedding] ✅ PASS

测试 3/3：Nex-N2-Pro 视觉能力（image_url 格式）★ 关键
  [Vision] ✅ PASS / ❌ FAIL

测试汇总
  llm          ✅ PASS
  embedding    ✅ PASS
  vision       ✅ PASS / ❌ FAIL
```

也可以只跑单项测试：
```bash
python test_connection.py --only vision
```

### 第 3 步：Vision API 专项验证（★ 关键）

这一步专门验证 Nex-N2-Pro 是否支持 OpenAI Vision API 的 `image_url` 输入格式：

```bash
python test_vision_capability.py
```

**判定逻辑：**
- ✅ 返回正常识别 → Nex-N2-Pro 可作 Vision 模型
- ❌ 报错含 `image_url not supported` / `invalid content format` → 不支持，需切换 GLM-4V

脚本会自动测试备选模型（GLM-4V）作为对照，并生成 `vision_test_report.json`。

### 第 4 步：RAG-Anything 标书解析

```bash
# 用 PDF 解析（测多模态，推荐）
python test_parse.py

# 或用 Markdown 解析（纯文本）
python test_parse.py --doc markdown
```

脚本会：
1. 用 `process_document_complete()` 解析标书 PDF
2. 对 6 个预设问题执行 `aquery()` 查询
3. 输出结果到 `parse_results.json`

**预设查询：**
| ID | 问题 | 期望 |
|----|------|------|
| qualification | 投标人的资质要求有哪些？ | 7 项 |
| performance | 投标人的业绩要求是什么？ | 3 项 |
| financial | 投标人的财务要求有哪些？ | 5 项 |
| personnel | 投标人的项目团队人员要求是什么？ | 5 项 |
| scoring | 评分标准是什么？各评分项的分值是多少？ | 6 项，总分 100 |
| supply_list | 供货清单有哪些设备？ | 5 项 |

### 第 5 步：评估解析效果

```bash
python evaluate_parse.py
```

对照标书样本的已知结构，评估三个维度：
1. **信息覆盖率**：关键信息点是否被解析出来
2. **表格结构保留率**：表格数据是否完整保留
3. **数值准确性**：关键数值是否准确

也可以只打印关键信息清单（不评估）：
```bash
python evaluate_parse.py --checklist
```

## 关键验证结论说明

### Nex-N2-Pro 是否支持 Vision API

这是本阶段最关键的验证点。RAG-Anything 的多模态解析依赖 Vision 模型识别 PDF 中的表格和图片。

- **如果支持** → 项目可基于 Nex-N2-Pro 开发，进入 Phase 3
- **如果不支持** → 切换到智谱 GLM-4V 或 OpenAI gpt-4o，修改 `config.yaml` 的 `vision.model`

判定方式：运行 `test_vision_capability.py`，查看输出的 `verdict` 字段：
- `SUPPORTED`：支持，可用
- `FALLBACK_OK`：主模型不支持但备选通过
- `ALL_FAILED`：都不支持
- `INCONCLUSIVE`：非格式问题，需检查 Key

## 故障排查

### raganything 安装失败（PaddleOCR 冲突）

PaddleOCR 是 raganything[all] 的可选依赖，可能与其他包冲突。降级方案：
```bash
pip install raganything  # 不带 [all]
```

### test_parse.py 报 ImportError

确保 raganything 和 lightrag 已安装：
```bash
pip install raganything lightrag-hku
```

### Vision 测试返回 401/403

检查 API Key 是否正确、账户是否有余额。硅基流动新用户有免费额度。

### test_parse.py 超时

DeepSeek 首次解析文档需要调用 LLM 抽取实体和构建知识图谱，可能需要 5-15 分钟。请耐心等待。
