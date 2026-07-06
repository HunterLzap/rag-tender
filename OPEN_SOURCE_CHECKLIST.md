# Open Source Checklist

本清单用于同步到 `D:\tools\RAG-Tender-Assistant-open-source` 前后核对，避免泄露本地真实业务资料。

## 必须保留

- 源码：`backend/app`、`frontend/src`、启动脚本、配置模板。
- 测试：`backend/test_*.py`、`frontend/tests`。
- 文档：`README.md`、`docs`、`PROJECT_PLAN.md`、`PROGRESS.md`、`AI_HANDOVER.md`。
- 示例：仅保留脱敏或生成样例，禁止放真实标书、企业资质、人员证件、合同、财报。
- 依赖清单：`backend/requirements.txt`、`frontend/package.json`、锁文件。

## 必须排除

- `data/` 下所有真实数据库、上传文件、日志、缓存、RAG 工作目录。
- `backend/.venv/`、`frontend/node_modules/`、`frontend/dist/`、`*.tsbuildinfo`。
- `.env`、`.env.local`、任何包含 API Key、密钥、账号、手机号、身份证号、企业真实资料的文件。
- `__pycache__/`、`.pytest_cache/`、`.vite/`、`*.log`、`output/`。

## 同步后检查

1. 确认目标目录不是生产运行目录，路径必须是 `D:\tools\RAG-Tender-Assistant-open-source`。
2. 在目标目录检查不存在 `data/tender_assistant.db`、上传文件、RAG workspace、日志。
3. 运行后端基础测试或至少导入检查。
4. 运行前端 `npm run build`。
5. 使用关键词扫描：`sk-`、`api_key`、`RAG_TENDER_SECRET_KEY`、`身份证`、`营业执照`、`授权委托书`、`tender_assistant.db`。
