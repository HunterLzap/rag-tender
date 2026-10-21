# 投标响应工作台

面向投标文件审阅和投标模板填写的工作台。核心目标是让每条要求都能回到原文、每个结论都有证据、每个填写建议都能人工接受或修改。

这不是通用文档问答，也不把向量相似度当作最终判断。系统把文档解析、要求提取、证据匹配、规则判定、人工复核和模板标注组织成一条可追踪的业务链路。

## 核心链路

```text
Project
  -> DocumentRevision / Page / Block / TableCell
  -> SourceSpan
  -> Requirement
  -> EvidenceItem / EvidenceFact
  -> Decision
  -> FillSlot / FillTarget / FillSuggestion
  -> AnnotationAsset
  -> ChecklistItem / Report
```

## 当前能力

- PDF 文本、坐标和表格解析，扫描页走视觉模型转写；不可识别时保留明确质量标记。
- DOCX、XLSX、CSV 基础解析。DOC 仅在安装了 LibreOffice 时转换。
- 页面级要求提取，模型必须返回 `block_id + quote`，服务端回查原文后才入库。
- 证据事实、确定性规则、模型语义评估和人工复核分层判定。
- 硬性要求缺少证据时默认进入 `needs_review`，不会自动放行。
- 投标截止日参与证书和日期规则判断。
- 投标模板填写位置识别，支持表格单元格、下划线字段和合成空行。
- 基于模板原页面渲染的标注 PNG，红框和编号直接叠加在原图上。
- 填写建议接受、修改、拒绝和审阅人记录。
- 自动生成交付检查项，处理后更新分析状态。
- 后台任务持久化、租约、重试、取消和 worker 崩溃恢复。
- SQLite WAL、Alembic 迁移和 API Key 本地加密。

## 不包含

- RAG-Anything、LightRAG、MinerU、PaddleOCR、Torch。
- 向量数据库主链路。
- 自动修改真实 DOCX/XLSX 并回写文件。当前 P0 是填写建议和原页面标注图，回写属于下一阶段。
- 用图像生成模型生成标书页面。标注图始终来自原页面渲染。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18、Vite、TypeScript、MUI、TanStack Query |
| API | FastAPI、Pydantic 2、SQLAlchemy 2 async |
| 数据 | SQLite WAL、Alembic |
| 文档 | pdfplumber、pypdfium2、python-docx、openpyxl、Pillow |
| 后台任务 | 自建 jobs 表 + 独立 worker |
| 模型 | OpenAI-compatible Chat Completions，文本和视觉模型分开配置 |

## 本地启动

要求：

- Python 3.13+
- Node.js 22+、pnpm
- 可选：LibreOffice（只有 `.doc` 转换需要）

安装后端：

```bash
cd backend
uv sync
cp ../.env.example ../.env
```

安装前端：

```bash
cd frontend
pnpm install
```

启动全部服务：

```bash
./start.sh
```

访问：

- 前端：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs

停止：

```bash
./stop.sh
```

开发时也可以分别运行：

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
cd backend && .venv/bin/python -m app.worker
cd frontend && pnpm dev
```

启动脚本会先执行 `alembic upgrade head`。已有 v2 开发库如果没有迁移版本，先在确认不需要迁移数据时重建开发库，或为它创建 baseline；不要把旧 RAG 数据库当作 v2 数据库直接使用。

## Docker

```bash
cp .env.example .env
docker compose up --build
```

默认前端端口为 `8088`，可用 `TENDER_HTTP_PORT` 修改。数据目录挂载在 `./data`。

## 模型配置

在前端「模型配置」页面填写：

- `base_url`：兼容 OpenAI Chat Completions 的地址，例如 `https://api.openai.com/v1`
- `text_model`：要求提取和语义评估模型
- `vision_model`：扫描页视觉转写模型，可选
- `api_key`：只保存 Fernet 加密结果

API Key 的主密钥来自 `TENDER_SECRET_KEY`。未配置时会在数据目录生成 `.secret_key`，该文件权限为 `0600`，不得提交。

可使用 `POST /api/v2/model-configs/test` 或页面的测试入口验证文本模型连接。

## 使用流程

1. 新建项目，上传招标文件和投标模板。
2. 设置投标截止日，并录入投标人、报价、工期等响应值。
3. 等待解析完成，启动分析。
4. 在「要求核对」中检查原文、证据和判定，提交人工复核。
5. 在「填写建议」中查看原模板标注图，接受或修改建议。
6. 在「交付检查」中逐项完成待办。
7. 导出 Markdown 检查报告。

## 验证

```bash
cd backend
uv run ruff check app tests alembic
uv run pytest -q

cd ../frontend
pnpm test
pnpm build
```

端到端测试覆盖：上传 PDF、worker 解析、mock 模型提取、判定、人工复核、填写计划、建议修改和标注图读取。

黄金集评测：

```bash
cd backend
uv run python -m app.evaluation_cli --help
```

## 数据与安全

- `data/`、上传文件、渲染页、导出图、SQLite 和日志都不提交。
- 模型输入中的文档内容按不可信数据处理，提示词要求忽略文档内的指令。
- 不把模型输出坐标直接当作页面坐标；标注坐标来自解析后的原文块或表格单元格。
- `needs_review` 是保守结果，不应被 UI 当作通过。

## 目录

```text
backend/
  app/
    api/           REST API
    domain/        文档 IR 和确定性规则
    services/      解析、提取、判定、填写、任务
    models.py      SQLAlchemy 领域模型
  alembic/         数据库迁移
  tests/           后端和端到端测试
frontend/
  src/
    components/    页面查看器
    pages/         项目、工作台、证据、设置
tests/evaluation/  黄金集样例
samples/           脱敏样例
```

## 许可证

MIT，见 `LICENSE`。
