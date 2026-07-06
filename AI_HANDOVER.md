# AI 交接指引（AI Handover）

> 🤖 **如果你是接手本项目的 AI 助手，请完整读本文件，然后按指示操作。**
> 本文件是项目唯一的「交接入口」，读完本文件你就知道：项目是什么、要读哪些文件、不能违反什么规则、当前该做什么。
>
> **用户使用方式**：换 AI 时，只需对新 AI 说一句话 ——
> > "读 `D:\projects\RAG-Tender Assistant\AI_HANDOVER.md`，然后告诉我你的理解"

---

## 一、这是什么项目（30 秒理解）

**RAG-Tender Assistant** —— 一套帮助招投标从业者**自动处理标书**的本地 Windows 工具：

```
上传标书 → RAG-Anything 解析 → 提取资质要求
                                  ↓
        与资质库资质比对（候选召回 + 字段级证据矩阵 + 保守判定）
                                  ↓
        符合的 → 自动填入投标模板（DOCX/XLSX/PDF）
        不符合/待确认 → 记录原因 + 证据矩阵 + 人工纠错沉淀
```

- **技术栈**：FastAPI（后端）+ React 18 + MUI 5（前端）+ SQLite + RAG-Anything
- **部署**：本地 Windows 单机，单人自用
- **配色**：淡紫色 `#7C4DFF` + 白色（不要改深色）
- **状态**：MVP 核心链路已打通，2026-07-03 已继续补齐轻量检查器、检查报告导出、LLM 调用记录与规则库页面细节；截至 2026-07-06，已再次完成每日文档同步，当前未发现 2026-07-05 之后的新代码变更，已确认风险仍是自定义规则归并接口尚未闭环。

---

## 二、必读文件清单（按顺序，共 6 个）

读完本文件后，**按以下顺序**读这 6 个文件。每个文件标注了「读什么」和「读多久」。

### 📖 第 1 步：进度记录（最重要，先读）

**文件**：`PROGRESS.md`（项目根目录）
**读什么**：
- 「当前状态」表格 —— 一眼看到项目走到哪一步
- 「进度时间线」 —— 完整开发历程
- 「遗留问题与待办」 —— 决定你下一步该做什么
- 「关键技术决策」表 —— **防止你重新讨论已定的事项**
- 「用户偏好」 —— 接手者必读，避免踩雷
**预计**：3 分钟

### 📖 第 2 步：项目入口文档

**文件**：`README.md`（项目根目录）
**读什么**：
- 「快速启动」—— 怎么跑起来
- 「项目目录结构」—— 文件都在哪
- 「技术栈」—— 用了什么
- 「API 端点一览」—— 当前常用入口与 `/docs` 的最新路由口径
- 「AI 接手指南」—— 代码模块入口
**预计**：3 分钟

### 📖 第 3 步：交付报告

**文件**：`docs/DELIVERY.md`
**读什么**：
- 完整文件清单（后端 31 个 + 前端 38 个）
- MVP 交付清单 + 2026-07-01 / 2026-07-02 后续重要增量
- 测试结果
- 已知问题（3 高 + 4 中 + 3 低）
**预计**：3 分钟

### 📖 第 4 步：产品需求

**文件**：`docs/PRD.md`
**读什么**：
- 产品目标 + 用户故事
- 11 项 P0 + 7 项 P1 + 4 项 P2 需求
- UI 配色规范
**预计**：5 分钟

### 📖 第 5 步：系统架构

**文件**：`docs/ARCHITECTURE.md`
**读什么**：
- 框架选型与理由
- 完整文件列表与行数预估
- 7 个数据模型（配合 `docs/class-diagram.mermaid`）
- 3 个核心流程时序图（配合 `docs/sequence-diagram.mermaid`）
- 任务分解 T01-T05
**预计**：8 分钟

### 📖 第 6 步：项目背景与技术方案

**文件**：`PROJECT_PLAN.md`（项目根目录）
**读什么**：
- 项目背景与核心目标
- 技术栈（最终采用方案）
- RAG-Anything 核心用法（原理）
- 成本预估
**预计**：3 分钟

> ⏱️ **总计**：约 25 分钟读完所有文档，即可完全理解项目。

---

## 三、必知约定（⚠️ 不能违反，违反会破坏用户体验）

### 🔒 数据安全（用户最敏感）

| 规则 | 说明 |
|:---|:---|
| **API Key 只在前端 UI 填写** | 绝不能写到 `config.yaml` 或任何配置文件 |
| **API Key 存 SQLite** | 加密存储（`enc:...`），主密钥来自 `RAG_TENDER_SECRET_KEY`，API 返回必须脱敏（`****abcd`） |
| **日志不能出现 Key** | 日志中替换为 `[REDACTED]` |
| **不要泄露主密钥** | `RAG_TENDER_SECRET_KEY` 不能写入代码、日志或开源仓库 |

### 🎨 UI 与体验

| 规则 | 说明 |
|:---|:---|
| **配色固定** | 淡紫色 `#7C4DFF` + 白色，**不要提议深色主题**（用户明确拒绝过） |
| **部署固定** | 本地 Windows 单机，**不要提议云部署 / 多用户 / 权限系统** |
| **使用者** | 单人自用，**不要提议团队协作功能** |

### 🛠 技术选型（已定，不要改）

| 决策点 | 选择 | 不要改的原因 |
|:---|:---|:---|
| 数据库 | SQLite | 本地单机零配置，用户明确不需要 PostgreSQL |
| 前端框架 | React 18 + MUI 5 | 生态成熟，已实现 |
| 文档解析 | PyPDF2 + python-docx 直接提取 | 用户显卡不支持 mineru VLM，纯文本方案 30 秒完成 |
| Embedding | BAAI/bge-m3（维度 1024） | GLM-Z1-9B 是 LLM 不是 Embedding，别搞混 |
| Office→PDF | LibreOffice headless | 已装、稳定 |
| 模板占位符 | Mustache 风格 `{{字段名}}` | 简单直观 |
| 长时任务 | FastAPI BackgroundTask + 前端轮询 | 简单够用 |

### 📂 路径约定

| 规则 | 说明 |
|:---|:---|
| **所有路径用相对路径** | 不要硬编码 `C:\Users\...`，用 `pathlib.Path(__file__).parent` 或环境变量 |
| **项目根目录** | `D:\projects\RAG-Tender Assistant\` |
| **后端** | `backend/` |
| **前端** | `frontend/` |
| **数据库** | `data/tender_assistant.db`（自动创建） |

### ✅ 修改代码后必做

```bash
# 后端验证（按本次实际维护的测试优先）
cd backend
.venv\Scripts\python.exe test_reclassification.py
.venv\Scripts\python.exe test_match_without_raganything.py

# 前端验证
cd frontend && npx tsc -b && npm run build
```

---

## 四、当前该做什么（接手后的第一步）

### ✅ 当前状态：核心链路收口 + 规则库主链路补齐（更新至 2026-07-06）

**当前不要再从 2026-06-25 的分类改造继续做起**。该阶段已经完成，并继续扩展到资质库、业绩库、匹配页、证据矩阵和错例库。

2026-07-06 文档同步结论补充：

- 今天未发现新的代码、配置、测试或说明文档变更。
- 当前功能状态、验证结论和遗留风险沿用 2026-07-04 / 2026-07-03 已记录内容。
- 因今天未重跑测试或页面回归，不要把“今日同步”理解为“今日重新验证通过”。

当前关键设计：

- 标书解析仍可能依赖 LLM 做需求结构化抽取。
- 资质/财务/人员/业绩解析以本地规则为主，LLM 作为补充兜底。
- 资质匹配只处理可由资质库证明的能力项：
  - 企业资质
  - 业绩
  - 财务资料
  - 人员资质
- 承诺/信用/报价/关联关系/无违法/不可兼任等条款不进入资质库匹配，应归入提交资料、响应承诺或待办清单。
- 匹配策略是“候选召回 + 字段级证据矩阵 + 保守判定”：
  - 相似度/LLM 只负责解析、候选召回或低置信辅助。
  - 最终 `matched` 必须有关键字段证据链支撑。
  - 缺字段、组合证据不完整、规则未覆盖时默认 `needs_review`。
  - 税收+社保要求必须分别有纳税和社保证据，不能只凭纳税证明自动通过。
  - 泛泛“真实有效业绩”不能仅凭业绩库存在项目自动通过。
- `/match` 是匹配汇总表；`/match/:id` 是右侧覆盖式抽屉明细，点击遮罩或返回图标回到汇总。
- `/corrections` 是错例库页面，展示人工确认沉淀的纠错记录。
- 人工确认匹配结果时会弹出修正原因输入框，后端写入 `match_corrections`。
- `/tenders/:id/checklist` 会展示投标待办清单；系统可识别保证金、截止时间、签章密封、正副本/装订/页码、样品演示等红线，并兼容旧数据补标。
- `/rules` 是规则库页面，当前包含：
  - 内置规则目录与启停。
  - 规则变更记录。
  - 基于人工纠错生成的规则建议。
  - 规则草案编辑、相似规则检测、复用已有规则、审核发布。
  - 已发布规则与草案/相似规则之间的关系追溯。
- 当前已知缺口：
  - 路由层已存在 `PUT /api/v1/rules/{rule_id}/merge`。
  - 但 `backend/app/services/rule_library_service.py` 还没有 `merge_custom_rule` 实现。
  - 所以“重复自定义规则归并到主规则”不要当成已可用能力对外承诺。

**当前验证状态**：
- `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen`：2026-07-04 已确认本机端口存在监听。
- `backend\.venv\Scripts\python.exe backend\test_api_key_encryption.py`：通过。
- `backend\.venv\Scripts\python.exe backend\test_llm_call_logging.py`：通过。
- `backend\.venv\Scripts\python.exe backend\test_checkers_and_reports.py`：通过。
- `backend\.venv\Scripts\python.exe backend\test_rule_library.py`：通过。
- `frontend npm run build`：通过，仅保留既有 chunk-size 警告。
- `backend\.venv\Scripts\python.exe backend\test_rule_library_api.py`：当前在自定义规则归并用例失败，失败原因是 `merge_custom_rule` 缺失。

### 如果用户说「继续开发」或「接着干」

1. 先读 `PROGRESS.md` 顶部“当前状态”和最新的 `2026-07-06`、`2026-07-05` 时间线。
2. 如果只是复测：确认服务在 8000/5173，进入 `/match` 点击“重新匹配”，展开明细查看“证据矩阵”。
3. 如果要验证错例库：在匹配明细中点“确认”，填写修正原因，提交后进入 `/corrections` 查看记录。
4. 如果要验证待办红线：进入标书核对或匹配明细查看待办清单，重点看“格式自定”误报是否已清理、红色“红线”标签是否只落在高风险项。
5. 如果要验证规则库：优先看 `/rules` 页面，确认“规则建议 → 草案 → 发布/复用 → 关系追溯”链路；当前不要把“归并”当成通过项。
6. 如果要改匹配：优先看 `backend/app/services/match_service.py` 的 `_should_match()`、`_verify_qualification_evidence()`、`_match_performance_requirement()`。
7. 如果要改规则库：优先看 `backend/app/services/rule_library_service.py`、`backend/app/api/rules.py`、`frontend/src/pages/RuleLibraryPage.tsx`。
8. 如果要改资质库：优先看 `frontend/src/pages/KnowledgePage.tsx`、`backend/app/services/knowledge_service.py`。

### 如果用户报告 Bug

1. 读完本文件 + `PROGRESS.md`
2. 按 BugFix 流程：定位文件 → 修复 → 跑 `test_smoke.py` 验证

### 如果用户要新功能

1. 读完本文件 + `PROGRESS.md` + `docs/PRD.md`
2. 判断是否在 P1/P2 需求池里
3. 按 SOP 流程：增量 PRD → 增量设计 → 实现 → 测试

### 如果用户问「项目怎么样了」

1. 读 `PROGRESS.md` 的「当前状态」表格
2. 直接回答：核心链路已打通；保守匹配、证据矩阵、人工纠错、错例库和规则库主链路已上线；当前待补的是规则归并接口

---

## 五、代码模块速查（需要改代码时看）

| 任务 | 入口文件 |
|:---|:---|
| 修改文档解析 | `backend/app/services/document_parser.py`（PyPDF2 文本提取） |
| 新增 API 端点 | `backend/app/api/*.py` + `main.py` 注册 |
| 修改数据模型 | `backend/app/models/*.py` + `database.py` 建表逻辑 |
| 调整匹配规则 | `backend/app/services/match_service.py` |
| 修改规则库 | `backend/app/services/rule_library_service.py` + `backend/app/api/rules.py` + `frontend/src/pages/RuleLibraryPage.tsx` |
| 修改 RAG 配置 | `backend/app/services/rag_service.py` |
| 修改标书解析 | `backend/app/services/tender_service.py` |
| 修改知识库解析 | `backend/app/services/knowledge_service.py` |
| 修改自动填写 | `backend/app/services/fill_service.py` |
| 修改 API 配置逻辑 | `backend/app/services/config_service.py` |
| 新增前端页面 | `frontend/src/pages/*.tsx` + `App.tsx` 路由 |
| 修改主题 | `frontend/src/theme.ts` |
| 添加 API 配置预设 | `backend/app/config.py` 的 `PROVIDER_PRESETS` |
| 修改 API 调用 | `frontend/src/api/*.ts` |

---

## 六、环境验证（开始工作前跑一遍）

```bash
# 1. 检查后端能导入
cd backend
python -c "from app.main import app; print('OK')"

# 2. 检查前端能编译
cd ../frontend
npx tsc -b && echo "OK"

# 3. 一键启动验证
cd ..
start.bat
# 浏览器访问 http://localhost:5173
```

如果以上都通过，环境正常，可以开始工作。

---

## 七、用户偏好（沟通风格）

1. **直接**：用户喜欢直接、不绕弯子的回答；不喜欢冗长解释
2. **数据安全**：用户对 API Key 极度敏感，**绝不能**把 Key 写到任何配置文件或日志
3. **路径**：所有项目文件必须放在 `D:\projects\RAG-Tender Assistant\`
4. **测试数据**：用 `samples/JSZC-320508-JDJS-G2026-0002采购文件.doc` 作为真实测试标书
5. **配色**：淡紫色 `#7C4DFF` + 白色，不要提议深色主题
6. **部署**：本地 Windows 单机，不要提议云部署
7. **使用者**：单人自用，不要提议多用户/权限系统

---

## 八、文档地图（一图速览）

```
AI_HANDOVER.md ◀── 你正在读的文件（唯一入口）
    │
    ├── PROGRESS.md          ← 进度 + 遗留问题（第 1 步读）
    ├── README.md            ← 项目入口 + 快速启动（第 2 步读）
    ├── docs/
    │   ├── REQUIREMENT_RECLASSIFICATION_PLAN.md  ← 历史改造方案（需求分类阶段参考）
    │   ├── DELIVERY.md      ← 交付报告（第 3 步读）
    │   ├── PRD.md           ← 产品需求（第 4 步读）
    │   ├── ARCHITECTURE.md  ← 系统架构（第 5 步读）
    │   ├── class-diagram.mermaid       ← 类图
    │   └── sequence-diagram.mermaid    ← 时序图
    └── PROJECT_PLAN.md      ← 项目背景（第 6 步读）
```

---

## 九、读完本文件后，你应该能回答

- [ ] 项目是做什么的？（标书自动分析）
- [ ] 用什么技术栈？（FastAPI + React + RAG-Anything + SQLite）
- [ ] 当前进度？（核心链路已打通，保守匹配/证据矩阵/错例库/规则库主链路已上线）
- [ ] 下一步做什么？（先补规则归并接口，再继续补规则库、废标红线检查、业绩证据包或错例复盘能力）
- [ ] 不能违反什么约定？（API Key 安全 / 配色 / 部署方式 / 路径）
- [ ] 代码在哪里改？（见第五节模块速查）

如果以上都能回答，你已经准备好接手了。开始工作吧。

---

> 📝 本文件维护规则：
> - 每次项目有重大变更（新功能 / 架构调整 / 关键决策）时更新本文件
> - 「当前该做什么」章节随项目进展实时更新
> - 保持简洁，本文件是入口，不是百科全书 —— 详细信息在各自专项文档里
