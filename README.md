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
- 离线人工工作台：不调用模型也能补充有原文依据的要求、校正扫描页文字、框选填写位置、复核证据和导出结果。
- 按页小批提取（每批至多 8 个块、约 6000 字符），模型必须返回 `block_id + quote`；回查原文并逐页入库。
- 证据事实、确定性规则、模型语义评估和人工复核分层判定。
- 硬性要求缺少证据时默认进入 `needs_review`，不会自动放行。
- 投标截止日参与证书和日期规则判断。
- 保留 PDF 空单元格及合并单元格的真实坐标，识别下划线、空括号、复选框和签章提示。
- 基于模板原页生成标注 PNG，建议值直接绘制到对应空单元格，支持中文、换行和字号适配；完整内容显示在原页外的侧栏。
- 只有表头而没有填写行时明确提示确认位置，不凭空绘制填写行。
- 填写建议接受、修改、拒绝和审阅人记录。
- 自动生成交付检查项，处理后更新分析状态。
- 资料或证据变化后旧结论标记待重新核对；可重跑确定性规则，不重复模型提取。
- 导出 ZIP 资料包：检查报告、填写内容清单及各页原图标注。
- 后台任务持久化、租约、取消和 worker 崩溃恢复；分析失败不自动重跑，已保存的页面结果保留。
- SQLite WAL、Alembic 迁移和 API Key 本地加密。

## 不包含

- RAG-Anything、LightRAG、MinerU、PaddleOCR、Torch。
- 向量数据库主链路。
- 自动修改真实 DOCX/XLSX 并回写文件。当前 P0 是填写建议和原页面标注图，回写属于下一阶段。
- 用图像生成模型生成标书页面。标注图始终来自原页面渲染。

## 当前验收边界

- 已验证离线业务流程与模拟模型链路；真实服务的接口兼容性、提取准确率及扫描页转写质量尚未进行最终验收。真实模型调用保持关闭。
- 固定原页标注图用于 PDF 和转换后的 DOC。DOCX、XLSX、CSV 提供结构化文字与表格查看，原页图片需要上传对应 PDF。
- 扫描页文字转写不等于表格坐标准确。复杂扫描模板可先人工校正文字，再手工框选实际填写区域。

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

启动脚本会先校验 v2 数据库结构，为尚未记录迁移版本的 v2 开发库建立 baseline，再执行 `alembic upgrade head`。旧 RAG 数据库不在此迁移范围内。

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

本地默认启用离线保护：服务不会发起真实模型请求。完成功能开发后，如需做真实模型验收，必须显式设置 `TENDER_LIVE_MODEL_CALLS=true`，并只对确认过的小样例运行。连接测试也受此开关控制。

开发验证使用模拟模型。网络错误或 JSON 校验失败直接终止；只有明确的输出截断会拆小当前批次，不会因任意异常扩散为逐块调用。扫描页未配置视觉模型或调用被禁用时，会保留为人工复核项。

## 使用流程

1. 新建项目，上传招标文件和投标模板。
2. 设置投标截止日，并录入投标人、报价、工期等响应值。
3. 等待解析完成，启动模型分析；未启用模型时选择「新建人工核对与填写」。
4. 在「要求核对」中检查原文、证据和判定，提交人工复核。
5. 在「填写建议」中查看原模板标注图，接受或修改建议。
6. 在「交付检查」中逐项完成待办。
7. 导出检查报告，或下载包含填写清单和原页标注图的 ZIP 资料包。

扫描页没有文字时，可在「查看原文」中人工校正本页文字。自动识别遗漏的要求可在工作台手工补充；漏识别或位置不准的字段可在「填写建议」中手工添加、框选、修正或移除。以上操作均不调用模型。

## 验证

```bash
cd backend
uv run ruff check app tests alembic
uv run pytest -q

cd ../frontend
pnpm test
pnpm build
```

端到端测试覆盖：上传 PDF、worker 解析、mock 模型提取、判定、人工复核、真实空单元格定位、建议修改后重绘及重建保留审阅内容。全部离线运行。

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
