# RAG-Tender Assistant — 标书自动分析辅助系统

> 基于 RAG-Anything 二开，实现标书解析 → 资质匹配 → 自动填写的全流程工具

---

## 一、项目概述

### 1.1 背景

参与招投标过程中，企业需要反复人工阅读标书、核对自身资质、判断是否满足要求、手动填写内容。这个流程重复性强、耗时且容易遗漏。现有工具多是通用文档管理，缺乏专门针对招投标场景的"阅标 → 匹配 → 填写"一站式解决方案。

### 1.2 核心目标

开发一套工具，自动完成以下流程：

```
接收标书 → 解析标书内容 → 提取资质要求
                          ↓
              与公司已有资质库进行比对
                          ↓
          ┌─ 符合要求 → 自动填写对应内容
          └─ 不符合   → 跳过并记录原因
```

### 1.3 基础项目

- **上游项目**：[HKUDS/RAG-Anything](https://github.com/HKUDS/RAG-Anything)
- **定位**：基于 RAG-Anything 的多模态文档解析能力进行二次开发
- **许可**：MIT License

---

## 二、技术方案

### 2.1 系统架构（最终实现，详见 `docs/ARCHITECTURE.md`）

```
┌─────────────────────────────────────────────────────────────────┐
│              前端 React SPA（淡紫色主题 #7C4DFF）                  │
│  页面：Dashboard / Tender / Knowledge / Match / Corrections / Settings │
│  7 组件：Layout / Sidebar / ApiConfigDialog / FileUploader 等    │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP REST (/api/v1/*)
┌────────────────────────▼────────────────────────────────────────┐
│                   FastAPI 后端（多业务 API 端点）                   │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ 标书解析  │  │ 知识库    │  │ 匹配引擎  │  │ 自动填写模块   │  │
│  │ Service  │  │ Service  │  │ Service  │  │ Service       │  │
│  └─────┬────┘  └────┬─────┘  └────┬─────┘  └────────┬───────┘  │
│        │             │             │                  │          │
│  ┌─────▼─────────────▼─────────────▼──────────────────▼──────┐  │
│  │     RAGAnything 单例 + 规则引擎 + 字段级证据矩阵           │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐  │
│  │     SQLite（tender_assistant.db，本地业务表 + 幂等迁移）    │  │
│  │  tenders / requirements / knowledge_files / qualifications │  │
│  │  match_results / match_corrections / api_configs / fill_templates │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
         │                                          │
    ┌────▼────┐                              ┌──────▼──────┐
    │ DeepSeek │                              │ 硅基流动     │
    │ LLM API  │                              │ Emb+Vision  │
    └─────────┘                              └─────────────┘
```

### 2.2 技术栈（最终采用，详见 `docs/ARCHITECTURE.md`）

| 层次 | 技术 | 用途 |
|:---|:---|:---|
| **文档解析** | RAG-Anything 1.3.1 + MinerU 3.4.0 | PDF/Office 文档结构提取、OCR（内置 PaddleOCR） |
| **知识图谱** | LightRAG 1.5.3（RAG-Anything 内置） | 实体提取、跨模态关系发现、语义检索 |
| **LLM** | DeepSeek（deepseek-chat） | 文本推理、条件判断、要求提取 |
| **Embedding** | 硅基流动 BAAI/bge-m3（维度 1024） | 语义向量化 |
| **Vision** | 硅基流动 nex-agi/Nex-N2-Pro（限免） | 标书中图表/扫描件分析（⚠️ 未实测，备选 GLM-4V） |
| **后端框架** | FastAPI + uvicorn | REST API 封装 |
| **前端框架** | React 18 + Vite + MUI 5 + Tailwind CSS | 管理界面（淡紫色 #7C4DFF 主题） |
| **数据库** | SQLite（aiosqlite） | 本地存储（7 张表） |
| **文档转换** | LibreOffice 26.2 headless | Office→PDF 转换 |
| **文档生成** | python-docx + openpyxl + pdfplumber | DOCX/XLSX/PDF 模板填写 |

> ⚠️ 本节为最终采用方案。早期版本提到的 gpt-4o-mini / text-embedding-3-large / PostgreSQL 等均已弃用，以本表为准。

### 2.3 核心流程

#### 阶段 1：标书解析
1. 上传标书（PDF / DOCX / PPTX）
2. LibreOffice 自动将 Office 文档转为 PDF
3. MinerU 解析 PDF，提取文字、表格、图片
4. LightRAG 构建知识图谱，识别实体关系

#### 阶段 2：资质提取
1. 通过 LLM 分析标书中所有资质要求
2. 分类提取（硬性资质、人员要求、业绩要求、财务要求等）
3. 记录要求的具体参数（如注册资金 ≥ 1000 万）

#### 阶段 3：匹配决策
1. 将标书要求与资质库/业绩库做候选召回（本地字段、关键词、同义词、语义辅助）
2. 精确条件使用规则引擎和字段级证据矩阵校验
3. 相似度只用于候选召回，不直接决定通过
4. 输出匹配结果：通过 / 不通过 / 需人工确认
5. 缺字段、证据链不完整、规则未覆盖时默认需人工确认
6. 人工确认会沉淀错例记录，后续用于补规则

#### 阶段 4：自动填写
1. 通过项 → 从资质库提取对应信息
2. 使用 python-docx 写入标书模板对应位置
3. 生成填写后的文档

---

## 三、环境准备

### 3.1 已就绪环境

| 组件 | 状态 | 说明 |
|:---|:---|:---|
| **Python** | ✅ 就绪 | 推荐 3.13.12，需加入 PATH |
| **Node.js** | ✅ 就绪 | 推荐 22.22.2，需加入 PATH |
| **LibreOffice** | ✅ 已安装并初始化 | 26.2+，需加入系统 PATH |
| **Python venv** | ✅ 已创建 | 在 `backend/` 目录下运行 `python -m venv venv` 创建 |
| **前端依赖** | ✅ 已安装 | `cd frontend && npm install` |

> 💡 **接手者注意**：本表不再列出特定用户的绝对路径。请用 `where python` / `where node` / `where soffice` 在你自己的环境确认路径。

### 3.2 需要准备的 API（用户在前端 UI 填写，不写配置文件）

| API | 用途 | 推荐模型 | 备注 |
|:---|:---|:---|:---|
| **LLM API** | 文本推理、条件判断 | DeepSeek（deepseek-chat） | **刚需**，OpenAI 兼容接口 |
| **Embedding API** | 文本向量化 | 硅基流动 BAAI/bge-m3 | 维度 1024 |
| **Vision API** | 标书中图表/扫描件分析 | 硅基流动 nex-agi/Nex-N2-Pro | ⚠️ 限免模型，未实测 image_url 支持，备选 GLM-4V |

> ⚠️ **API Key 安全规则**（用户明确要求）：
> - Key 只在前端 UI 的「API 配置」弹窗填写
> - Key 使用 `RAG_TENDER_SECRET_KEY` 加密后存储在本地 SQLite（`enc:...`）
> - API 返回时脱敏（仅显示末 4 位，如 `****abcd`）
> - 日志中替换为 `[REDACTED]`
> - **绝不能**把 Key 写到 `config.yaml` 或任何配置文件

### 3.3 LibreOffice 调用方式

```python
import os

# 方式一：设置 PATH（推荐，在初始化 RAGAnything 前执行）
os.environ["PATH"] += r";C:\Program Files\LibreOffice\program"

# 方式二：直接指定调用路径
soffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"

# 命令行调用方式
# soffice.exe -env:UserInstallation="file:///path/to/.libreoffice-init"
#           --headless --norestore
#           --convert-to pdf --outdir "输出目录" "源文件"
```

---

## 四、RAG-Anything 核心用法

> ⚠️ 本节为早期验证用的示例。**实际项目中已封装到 `backend/app/services/rag_service.py`**，不需要手动初始化。本节保留供理解原理用。

### 4.1 安装

```bash
pip install 'raganything[all]'
```

实际项目依赖见 `backend/requirements.txt`。

### 4.2 核心类

| 类/方法 | 作用 |
|:---|:---|
| `RAGAnything` | 主类，初始化和执行 |
| `RAGAnythingConfig` | 配置（工作目录、解析器选择等） |
| `process_document_complete()` | 端到端处理单个文档 |
| `process_folder_complete()` | 批量处理文件夹 |
| `aquery()` | 文本查询（hybrid/local/global/naive 模式） |
| `insert_content_list()` | 直接插入预解析内容 |
| `ImageModalProcessor` | 图片内容处理器 |
| `TableModalProcessor` | 表格内容处理器 |

### 4.3 初始化示例（原理说明，实际见 rag_service.py）

```python
from raganything import RAGAnything, RAGAnythingConfig
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from functools import partial

config = RAGAnythingConfig(
    working_dir="./rag_storage",
    parser="mineru",
    enable_image_processing=True,
    enable_table_processing=True,
)

# LLM 函数（实际从 SQLite 读 base_url / api_key / model_name）
def llm_model_func(prompt, **kwargs):
    return openai_complete_if_cache(
        "deepseek-chat", prompt,
        api_key="YOUR_KEY", base_url="https://api.deepseek.com/v1", **kwargs
    )

# Embedding 函数（实际从 SQLite 读配置）
embedding_func = EmbeddingFunc(
    embedding_dim=1024, max_token_size=8192,
    func=partial(openai_embed.func, model="BAAI/bge-m3",
                 api_key="YOUR_KEY", base_url="https://api.siliconflow.cn/v1"),
)

rag = RAGAnything(
    config=config,
    llm_model_func=llm_model_func,
    embedding_func=embedding_func,
)
```

> 💡 **接手者注意**：实际代码中，`api_key` / `base_url` / `model_name` 全部从 SQLite 的 `api_configs` 表读取，不在代码里硬编码。详见 `backend/app/services/rag_service.py`。

---

## 五、开发计划与实际进度

> ⚠️ 本节为**计划与实际对照**。详细进度见 `PROGRESS.md`。

### Phase 1：基础环境搭建 ✅ 已完成
- [x] 安装 LibreOffice 26.2 并验证文档转换
- [x] 配置 Python 虚拟环境（3.13.12）
- [x] 安装 Node.js（22.22.2）
- [x] 确认系统依赖

### Phase 2：RAG-Anything 验证 ✅ 已完成
- [x] 安装 `raganything[all]` 1.3.1 + lightrag-hku 1.5.3 + mineru 3.4.0
- [x] 验证 RAG-Anything API 全部可用（process_document_complete / aquery 等）
- [x] 安装 paddlepaddle 3.3.1（paddleocr 后端）
- [ ] ⚠️ 用真实 API Key 测试解析效果（等用户填 Key）
- [ ] ⚠️ 验证 Nex-N2-Pro 的 image_url 支持（等用户填 Key）

### Phase 3：PRD + 架构设计 ✅ 已完成
- [x] 完成 `docs/PRD.md` v1.1（11 P0 + 7 P1 + 4 P2）
- [x] 完成 `docs/ARCHITECTURE.md`（904 行，含文件列表/类图/时序图/任务分解）
- [x] 完成任务分解 T01-T05

### Phase 4：代码实现 ✅ 已完成
- [x] T01 项目骨架 + T02 数据层 + API 配置（27 个 Python 文件）
- [x] T03 后端核心业务（10 个新文件 + 2 个更新，21 个路由全部可用）
- [x] T04 前端开发（38 个文件，5 页面 + 7 组件）
- [x] T05 集成联调（start.bat 一键启动）

### Phase 5：测试与交付 ✅ 已完成
- [x] 后端烟雾测试通过
- [x] 前端 TypeScript 编译零错误
- [x] 前端生产构建成功
- [x] 交付报告 `docs/DELIVERY.md`
- [ ] ⚠️ 端到端真实标书验证（等用户填 Key）

### 后续阶段（待规划）
- [x] 匹配引擎保守判定：候选召回 + 字段级证据矩阵 + 缺证据默认待确认
- [x] 人工纠错沉淀：`match_corrections` + 错例库页面
- [x] 规则库基础闭环：规则目录、启停、错例建议、草案编辑/审核、相似规则复用、关系追溯
- [ ] 规则库归并与规则沉淀深化：补齐自定义规则归并接口，并继续把高频规则从代码沉淀为可配置规则
- [x] 投标待办红线识别：保证金、截止时间、签章密封、正副本/装订/页码、样品演示等高风险项
- [ ] 废标红线检查扩展：授权书、报价日期、暗标敏感信息等更细规则
- [ ] 业绩证据包完整性：合同首页、金额页、签字盖章页、验收证明等
- [ ] 资质到期/缺字段提醒
- [ ] PDF 模板填写格式保留优化

---

## 六、API 接口设计（初稿，实际以代码为准）

> ⚠️ 本节为当前常用接口摘要，不再用固定数量口径；完整路由以代码和 http://127.0.0.1:8000/docs 为准。当前已包含匹配进度、人工纠错/错例记录、技术响应、投标待办、业绩项目、规则库治理等接口。

```http
POST /api/v1/tenders/upload                   上传标书
GET  /api/v1/tenders                          标书列表
GET  /api/v1/tenders/{id}                     标书详情
DELETE /api/v1/tenders/{id}                   删除标书
POST /api/v1/tenders/{id}/parse               触发标书解析
GET  /api/v1/tenders/{id}/status              解析进度
GET  /api/v1/tenders/{id}/requirements        获取解析结果（5 类要求）
GET  /api/v1/tenders/{id}/technical           技术响应表
GET  /api/v1/tenders/{id}/checklist           投标待办清单
POST /api/v1/tenders/{id}/checklist           手动新增待办项

GET  /api/v1/knowledge/files                  知识库文件列表
POST /api/v1/knowledge/upload                 上传知识库文件
GET  /api/v1/knowledge/qualifications         资质列表
POST /api/v1/knowledge/qualifications         新增资质
GET  /api/v1/performance/projects             业绩项目列表

POST /api/v1/match/{tender_id}                触发匹配
GET  /api/v1/match/{tender_id}                匹配结果
GET  /api/v1/match/{tender_id}/status         匹配进度
GET  /api/v1/match/corrections                人工纠错/错例记录

GET  /api/v1/rules                            规则目录（内置 + 已发布自定义规则）
GET  /api/v1/rules/changes                    规则变更记录
GET  /api/v1/rules/suggestions                基于错例生成的规则建议
PUT  /api/v1/rules/suggestions/{id}/review    审核规则建议
GET  /api/v1/rules/drafts                     规则草案列表
PUT  /api/v1/rules/drafts/{id}                编辑规则草案
GET  /api/v1/rules/drafts/{id}/similar        检测相似规则
PUT  /api/v1/rules/drafts/{id}/reuse          复用已有规则
PUT  /api/v1/rules/drafts/{id}/review         发布/驳回规则草案
GET  /api/v1/rules/{rule_id}/relations        查看规则关系追溯
PUT  /api/v1/rules/{rule_id}/enabled          开启/关闭规则
# 待补闭环：PUT /api/v1/rules/{rule_id}/merge 已暴露路由，但当前服务层实现待补

POST /api/v1/fill/{tender_id}                 触发自动填写
GET  /api/v1/fill/{tender_id}/download        下载填写结果

GET  /api/v1/config                           获取 API 配置（脱敏）
POST /api/v1/config                           保存 API 配置
POST /api/v1/config/test                      测试 API 连接
GET  /api/v1/config/presets                   供应商预设

GET  /api/v1/health                           健康检查
```

---

## 七、成本预估

| 项目 | 说明 | 预估费用 |
|:---|:---|:---|
| **DeepSeek LLM API** | 每份标书约 50-200K tokens | ~¥0.1-1/份 |
| **硅基流动 Embedding** | BGE-M3，限免额度内 | 免费（限免内） |
| **硅基流动 Vision** | Nex-N2-Pro，限免 | 免费（限免内，可能转收费） |
| **服务器** | 纯 API 调用无需 GPU | ¥0（本地运行） |
| **LibreOffice** | 开源免费 | 免费 |
| **RAG-Anything** | MIT License | 免费 |
| **数据库** | SQLite 本地 | 免费 |

---

## 八、注意事项与风险

### 8.1 技术风险
- **标书格式多样性**：扫描件/图片 PDF 的 OCR 精度是关键瓶颈
- **匹配准确性**：模糊表述（如"类似项目经验"）依赖 LLM 推理能力
- **RAG-Anything 无内置 API**：所有 REST 接口需自行封装

### 8.2 数据安全
- 标书涉及商业机密，需注意 LLM API 的数据隐私条款
- 考虑使用 Azure OpenAI 或国产大模型部署在内网

### 8.3 依赖说明
- **LibreOffice 仅用于 Office 文档 → PDF 转换**，不影响日常使用 WPS
- 如果标书已是 PDF 格式，可直接跳过 LibreOffice
- RAG-Anything 支持换用 Docling 解析器（对 docx 原生支持，不依赖 LibreOffice）

---

## 九、相关资源

- [RAG-Anything GitHub](https://github.com/HKUDS/RAG-Anything)
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [RAG-Anything 论文](http://arxiv.org/abs/2510.12323)
- [LibreOffice 下载](https://www.libreoffice.org/download/download/)
- [DeepSeek 平台](https://platform.deepseek.com/)
- [硅基流动平台](https://cloud.siliconflow.cn/)

---

## 十、AI 接手须知

如果你是接手本项目的 AI 助手，请**务必**按以下顺序阅读：

1. **`README.md`** — 项目入口、快速启动、目录结构、AI 接手指南（**最重要**）
2. **`PROGRESS.md`** — 当前进度、已完成/遗留事项（决定下一步做什么）
3. **`docs/DELIVERY.md`** — 交付清单、API 端点、已知问题
4. **`docs/PRD.md`** — 详细需求（11 P0 + 7 P1 + 4 P2）
5. **`docs/ARCHITECTURE.md`** — 系统架构、文件列表、数据模型
6. 本文件 — 项目背景与技术方案

### 关键约定（不要违反）

- ✅ 所有路径用相对路径或环境变量，**不要硬编码** `C:\Users\...`
- ✅ API Key 只在前端 UI 填写，存 SQLite，**不要写到配置文件**
- ✅ 配色固定淡紫色 `#7C4DFF` + 白色，**不要改深色主题**
- ✅ 数据库用 SQLite，**不要提议 PostgreSQL/MySQL**
- ✅ 部署在本地 Windows，**不要提议云部署**
- ✅ 修改代码后跑测试：后端 `python test_smoke.py`，前端 `npx tsc -b && npm run build`

---

> 文档版本：v1.3（已于 2026-07-06 复核，当前实现状态未变）
> 创建日期：2026-06-22
> 最后更新：2026-07-06
> 基于 HKUDS/RAG-Anything 二次开发
