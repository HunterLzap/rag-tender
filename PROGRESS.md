# RAG-Tender Assistant — 项目进度记录

> 本文件记录项目从立项到当前的所有关键进度，**任何接手者请先读本文件**。
> 维护原则：每完成一个阶段或解决一个重要问题就追加一条，不修改历史记录。
>
> 💡 **新 AI 接手请先读 `AI_HANDOVER.md`**（项目唯一的交接入口文档），它会指引你读哪些文件。

---

## 🎯 当前状态（一图速览）

| 维度 | 状态 | 说明 |
|:---|:---|:---|
| **整体进度** | ✅ MVP 交付 + 风险审查链路增强 | 标书解析、资质库、业绩库、保守匹配、证据矩阵、人工纠错、错例库均已打通 |
| **可启动** | ✅ 是 | `start.bat` 一键启动 |
| **可使用** | ✅ 是 | 本地规则主链路可用；LLM API 续费后建议重新跑一遍解析/匹配复核 |
| **文档解析** | ✅ 已优化 | PyPDF2/python-docx 直接提取文本；LLM 负责标书需求结构化抽取 |
| **真实标书验证** | ✅ 通过 | 当前真实标书 `id=14/15` 已解析；`id=15` 已用新保守匹配重跑，2 条结果均转为待确认 |
| **资质库** | ✅ 已重构 | 文件列表/资质列表分页、批量删除、分类表头、人员资料类型细分、文件预览已完成 |
| **业绩库** | ✅ 已独立 | 业绩项目独立 Tab，支持业绩文件上传、总表导入、文件关联 |
| **匹配设计** | ✅ 已增强 | 相似度只负责候选召回；最终按字段级证据矩阵保守判定；缺字段/组合证据不完整时进入待确认 |
| **错例沉淀** | ✅ 已上线 | 人工确认会记录原判断、人工修正、修正原因、证据快照；前端新增“错例库”页面 |
| **红线待办** | ✅ 已增强 | 投标待办清单可自动识别保证金、截止时间、签章密封、正副本/装订/页码、样品演示等高风险项；旧数据读取时会补标并清理旧规则误标 |
| **规则库** | ✅ 已起步 | 已打通规则目录、启停、变更留痕、错例建议、草案编辑/审核、相似规则复用、关系追溯；当前仍有自定义规则归并接口待补齐 |
| **当前服务** | ▶️ 状态待确认 | 最近一次确认是在 2026-07-04 文档同步时，本机 8000 / 5173 端口存在监听；2026-07-06 本次仍仅做文档同步，未重新复测页面与接口交互 |

---

## 📅 进度时间线

### 2026-07-06：每日文档同步（无新增代码变更）✅

- 依据工作区文件最后修改时间再次复核：今天未发现新的代码、配置、测试或说明文档落盘变更。
- 自上次同步后，工作区内最近一次实际文件写入仍集中在 2026-07-05 的文档记录文件：
  - `PROGRESS.md`
  - `AI_HANDOVER.md`
  - `PROJECT_PLAN.md`
  - `docs/DELIVERY.md`
- 本次同步处理：
  - 更新 `PROGRESS.md` 顶部状态与今日时间线。
  - 更新 `AI_HANDOVER.md` 的接手状态日期与口径说明。
  - 更新 `PROJECT_PLAN.md` 文档复核日期。
  - 在 `docs/DELIVERY.md` 追加 2026-07-06 文档同步说明。
- 今日结论维持不变：
  - 当前没有证据表明 2026-07-05 之后出现新的功能实现、缺陷修复或接口调整。
  - API Key 安全口径保持不变：SQLite 加密存储（`enc:...`）+ API 返回脱敏 + 日志 `[REDACTED]` + 主密钥来自 `RAG_TENDER_SECRET_KEY`。
  - 规则库风险保持不变：`PUT /api/v1/rules/{rule_id}/merge` 路由虽已暴露，但服务层仍缺少 `merge_custom_rule`，归并链路暂不能写成已完成。
- 待确认：
  - 今天未重跑任何后端/前端测试，也未重新检查 8000 / 5173 端口监听状态；当前验证结论仍以上一次 2026-07-04 / 2026-07-03 的记录为准。

### 2026-07-05：每日文档同步（无新增代码变更）✅

- 依据文件最后修改时间复核工作区：今天未发现新的代码、配置、测试或说明文档落盘变更。
- 自上次同步后新增/修改文件仅有 2026-07-04 写入的文档：
  - `PROGRESS.md`
  - `AI_HANDOVER.md`
  - `PROJECT_PLAN.md`
  - `docs/DELIVERY.md`
- 本次同步处理：
  - 更新 `PROGRESS.md` 顶部状态与今日时间线。
  - 更新 `AI_HANDOVER.md` 的接手状态日期与口径说明。
  - 更新 `PROJECT_PLAN.md` 文档版本时间。
  - 在 `docs/DELIVERY.md` 追加 2026-07-05 文档同步说明。
- 今日结论维持不变：
  - 当前没有证据表明 2026-07-04 之后出现新的功能实现、缺陷修复或接口调整。
  - API Key 安全口径保持不变：SQLite 加密存储（`enc:...`）+ API 返回脱敏 + 日志 `[REDACTED]` + 主密钥来自 `RAG_TENDER_SECRET_KEY`。
  - 规则库风险保持不变：`PUT /api/v1/rules/{rule_id}/merge` 路由虽已暴露，但服务层仍缺少 `merge_custom_rule`，归并链路暂不能写成已完成。
- 待确认：
  - 今天未重跑任何后端/前端测试，也未重新检查 8000 / 5173 端口监听状态；当前验证结论仍以上一次 2026-07-04 / 2026-07-03 的记录为准。

### 2026-07-04：每日文档同步与安全口径校正 ✅

- 根据 2026-07-03 实际代码与测试结果补做今日同步，确认今天暂无新增代码/配置改动，当前增量仍以前一日实现为准。
- 本次同步更新：
  - `PROGRESS.md`
  - `AI_HANDOVER.md`
  - `PROJECT_PLAN.md`
  - `docs/DELIVERY.md`
- 本次重点校正：
  - `PROJECT_PLAN.md` 中旧的“API Key 明文存 SQLite”表述已修正为当前实现：SQLite 加密存储（`enc:...`）+ API 返回脱敏 + 日志 `[REDACTED]` + 主密钥来自 `RAG_TENDER_SECRET_KEY`。
  - 各文档统一保留当前风险口径：`PUT /api/v1/rules/{rule_id}/merge` 路由已暴露，但服务层仍缺少 `merge_custom_rule`，归并链路暂不能写成已完成。
- 今日轻量核对结果：
  - `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen`：确认本机 8000 / 5173 存在监听。
  - `backend\.venv\Scripts\python.exe backend\test_api_key_encryption.py`：通过。
  - `backend\.venv\Scripts\python.exe backend\test_llm_call_logging.py`：通过。
  - `backend\.venv\Scripts\python.exe backend\test_checkers_and_reports.py`：通过。
- 待确认：
  - 今天未重新执行规则库归并失败用例，也未重新做前端页面级人工回归；因此仍沿用 2026-07-03 的风险判断，不把归并能力记为已验证通过。

### 2026-07-03：BidMaster-Pro 对比学习清单沉淀 ✅

- 对比公开项目 `guangshu100/BidMaster-Pro` 与当前项目定位：
  - BidMaster-Pro 更偏全流程平台骨架，覆盖 Agent/Skill、投标生成、投标检查、排版、资讯、RBAC、Electron 和 Docker。
  - 当前项目更偏本地单人使用的标书解析、资质库、保守匹配、证据矩阵、错例沉淀和规则库治理。
- 新增文档 `docs/BIDMASTER_PRO_LEARNINGS.md`，明确：
  - 值得学习：Skill 插件化、全流程阶段设计、检查项覆盖、LLM Gateway、项目化数据模型、桌面端包装。
  - 不建议照搬：PostgreSQL/Redis/MinIO/Celery 重型基础设施、完整 Agent 框架、纯 LLM 判断、一次性扩成全流程投标生成平台。
  - 后续任务：轻量检查器接口、扩展红线待办、检查报告导出、LLM 调用记录、补齐 `merge_custom_rule`。

### 2026-07-03：文档同步与规则库回归核对 ✅

- 按 2026-07-02 实际代码变更，重新核对并同步：
  - `PROGRESS.md`
  - `AI_HANDOVER.md`
  - `README.md`
  - `PROJECT_PLAN.md`
  - `docs/DELIVERY.md`
- 明确补记规则库当前已实现链路：
  - `GET /api/v1/rules/suggestions`：基于人工纠错生成规则建议。
  - `PUT /api/v1/rules/suggestions/{suggestion_id}/review`：处理建议采纳/忽略。
  - `GET /api/v1/rules/drafts`：查看规则草案。
  - `PUT /api/v1/rules/drafts/{draft_id}`：编辑待审核草案。
  - `GET /api/v1/rules/drafts/{draft_id}/similar`：发布前检测相似规则。
  - `PUT /api/v1/rules/drafts/{draft_id}/reuse`：复用已有规则，避免重复发布。
  - `PUT /api/v1/rules/drafts/{draft_id}/review`：审核并发布/驳回规则草案。
  - `GET /api/v1/rules/{rule_id}/relations`：查看规则复用/相似关系追溯。
- 回归核对结果：
  - `backend\.venv\Scripts\python.exe backend\test_rule_library.py`：通过。
  - `frontend npm run build`：通过，仅保留既有 chunk-size 警告。
  - `backend\.venv\Scripts\python.exe backend\test_rule_library_api.py`：未完全通过。
- 新发现并记录的风险：
  - 路由层已暴露 `PUT /api/v1/rules/{rule_id}/merge`。
  - 但 `backend/app/services/rule_library_service.py` 当前缺少 `merge_custom_rule` 实现。
  - 因此自定义规则“归并到主规则”链路尚未闭环，需后续补齐后再宣称可用。

### 2026-07-02：规则库目录、启停与建议/草案链路上线 ✅

- 新增后端规则库服务 `rule_library_service`，把当前已启用的内置规则以统一结构暴露：
  - `id`
  - `name`
  - `domain`
  - `rule_type`
  - `strictness`
  - `enabled`
  - `keywords`
  - `description`
  - `source`
  - `action`
- 新增 `GET /api/v1/rules`，当前返回 5 条内置红线规则：
  - 投标保证金红线
  - 提交截止时间红线
  - 签章密封红线
  - 正副本与装订红线
  - 样品演示红线
- 新增 `rule_overrides` 表，保存用户对内置规则的启停配置。
- 新增 `rule_change_logs` 表，记录规则启停变更：
  - 规则 ID
  - 原启用状态
  - 新启用状态
  - 变更原因
  - 变更时间
- 新增 `PUT /api/v1/rules/{rule_id}/enabled`：
  - 可单独关闭/开启某一条内置规则。
  - 支持提交变更原因。
  - 关闭后规则库页面立即显示禁用状态。
  - 投标待办红线识别会读取启停配置，避免“页面关了但业务仍命中”。
- 新增 `GET /api/v1/rules/changes`，按时间倒序返回规则变更记录。
- 新增基于错例沉淀的规则建议链路：
  - `GET /api/v1/rules/suggestions`：从 `match_corrections` 生成规则候选建议。
  - `PUT /api/v1/rules/suggestions/{suggestion_id}/review`：记录建议采纳/忽略状态和原因。
- 新增规则草案链路：
  - `GET /api/v1/rules/drafts`：查看待审核/已发布/已驳回草案。
  - `PUT /api/v1/rules/drafts/{draft_id}`：发布前编辑草案内容和说明。
  - `GET /api/v1/rules/drafts/{draft_id}/similar`：发布前检查与内置规则、自定义规则、其他草案的相似度。
  - `PUT /api/v1/rules/drafts/{draft_id}/reuse`：直接复用已有规则，避免重复发布。
  - `PUT /api/v1/rules/drafts/{draft_id}/review`：审核发布或驳回规则草案。
- 新增规则关系追溯：
  - `GET /api/v1/rules/{rule_id}/relations`：查看相似、复用、发布等关系。
- 前端新增“规则库”页面 `/rules` 和侧边栏入口：
  - 展示规则总数、启用数、严格规则数、红线规则数。
  - 表格展示规则 ID、业务域、严格度、关键词、说明、命中动作。
  - 新增启停开关；开关规则时弹窗填写变更原因。
  - 页面下方展示最近规则变更记录，便于追溯误关/误开。
  - 新增“规则建议”“规则草案”“变更记录”多 Tab 视图，支持建议审核、草案编辑、相似规则提示和复用已有规则。
- 红线待办判断改为复用同一份带 ID 的规则定义，避免展示规则和实际判断规则不一致。
- 验证：
  - `backend\.venv\Scripts\python.exe backend\test_rule_library.py`：通过。
  - `backend\.venv\Scripts\python.exe backend\test_checklist_red_flags.py`：通过。
  - `backend\.venv\Scripts\python.exe backend\test_reclassification.py`：81 项通过。
  - `frontend npm run build`：通过，仅保留既有 chunk-size 警告。
  - 真实服务 `GET http://127.0.0.1:8000/api/v1/rules` 返回 5 条规则。
  - 真实服务 `PUT /api/v1/rules/submission.red_flag.deposit/enabled` 已验证可关闭并恢复开启。
  - 真实服务 `GET /api/v1/rules/changes?limit=2` 已验证返回关闭/恢复记录和原因。
  - 截至 2026-07-03，`backend\.venv\Scripts\python.exe backend\test_rule_library_api.py` 在“自定义规则归并”用例失败；当前不要把归并链路写成已验证通过。

### 2026-07-01：投标待办红线规则增强 ✅

- 在 `submission_checklist_service` 中新增投标提交类红线识别：
  - 投标保证金/缴纳/逾期/无效投标。
  - 截止时间/递交截止/提交截止/不予受理。
  - 签字、签章、盖章、密封、封装。
  - 正本、副本、份数、目录、页码、装订。
  - 样品、演示、现场踏勘、述标、答辩。
- 待办清单首次初始化时会把命中的红线写入备注，格式为 `【红线】...`。
- 兼容旧数据：如果待办清单已经生成，`GET /api/v1/tenders/{id}/checklist` 会自动补充红线备注。
- 收紧误报规则：
  - “格式自定”不再算红线。
  - 旧规则误加的系统红线段会被清理，保留人工备注。
- 前端待办表新增“红线”视觉标识，命中项会在待办名称旁显示红色风险标签。
- 真实标书 `id=15` 读取待办后，之前因“格式自定”误标的 2 条红线已清理为 0 条红线。
- 新增测试：
  - `backend/test_checklist_red_flags.py`
  - `frontend/src/components/submissionChecklistRisk.ts`
  - `frontend/tests/submissionChecklistRisk.test.ts`
- 验证：
  - `backend\.venv\Scripts\python.exe backend\test_checklist_red_flags.py`：通过。
  - `backend\.venv\Scripts\python.exe backend\test_reclassification.py`：81 项通过。
  - `backend\.venv\Scripts\python.exe backend\test_match_without_raganything.py`：通过。
  - `frontend npm run build`：通过，仅保留既有 chunk-size 警告。
- 同步文档：
  - 已同步 `README.md`、`AI_HANDOVER.md`、`PROJECT_PLAN.md`、`docs/DELIVERY.md` 的当前接口与验证口径。
  - 明确区分 `2026-06-22` MVP 历史清单与 `2026-07-01` 当前实现状态，避免继续沿用“21 个端点”旧说法。

### 2026-07-01：保守匹配、证据矩阵与错例库上线 ✅

#### 背景

- 用户担心资质/业绩/财务/人员匹配存在“本来不满足却显示符合”的风险。
- 对比成熟标书分析、清标、智能评标产品后，确定本项目后续定位从“相似匹配”升级为“证据链核验”：
  - LLM/相似度只负责解析和候选召回。
  - 最终结论必须由字段级证据矩阵和规则核验得出。
  - 缺字段、证据不完整、规则未覆盖时默认 `needs_review`，不能自动 `matched`。

#### 后端匹配引擎

- `match_results` 新增 `evidence_items` JSON 字段，保存字段级证据矩阵。
- 新增 `MatchEvidenceItem` 模型：
  - `check_key`
  - `label`
  - `expected_value`
  - `actual_value`
  - `status`：`pass/fail/unknown`
  - `reason`
  - `critical`
- 新增保守核验逻辑 `_verify_qualification_evidence()`：
  - 证书类型
  - 持证主体/持证人员
  - 有效期
  - 适用范围
  - 等级
  - 纳税证明 + 社保证明组合要求
- 取消“相似度 ≥ 0.7 直接通过”的语义：
  - 相似度只决定候选资质。
  - 高相似候选仍需字段级证据核验。
  - 关键字段 `unknown/fail` 时不能自动通过。
- 业绩匹配收紧：
  - 有明确合同金额下限时，金额满足才可自动通过。
  - “真实有效业绩”这类缺少金额、时间、项目类型等可规则核验字段的要求，默认 `needs_review`。
  - 业绩分支也返回证据矩阵。

#### 错例沉淀

- 新增 `match_corrections` 表，人工确认时记录：
  - 原系统状态
  - 人工确认状态
  - 修正原因
  - tender/requirement/qualification 关联
  - evidence snapshot
  - 创建时间
- `confirm_match()` 从单纯更新 `confirmed_status` 改为“更新确认状态 + 写入错例记录”。
- 新增 `GET /api/v1/match/corrections`，按时间倒序返回错例记录，并关联标书标题、要求标题、资质名称。

#### 前端匹配页

- 匹配明细展开区新增“证据矩阵”：
  - 核验项
  - 招标要求
  - 我的证据
  - 结果
  - 说明
- 人工确认从直接点击改为弹窗确认，可填写“修正原因”。
- 业绩类结果没有 `qualification_id` 时，不再显示“资质库未找到”；若 `in_knowledge_base=true`，显示“业绩库候选项目”。
- 新增“错例库”页面：
  - 侧边栏入口 `/corrections`
  - 展示错例总数、人工改为符合/不符合/需确认统计
  - 展示原判断、人工修正、修正原因、关联标书/要求/资质

#### 真实问题修复

- 用户截图中 `id=15` 重新匹配后仍显示：
  - “依法缴纳税收和社保”仅命中“纳税证明”但显示符合。
  - “真实有效业绩”显示“资质库未找到”但状态为符合。
- 定位结果：
  - 后端旧进程未重启，真实数据库也未迁移 `evidence_items`。
  - 旧业绩逻辑在 `required_amount is None` 时会把任意业绩项目当作符合。
  - 旧财务/社保组合逻辑未要求税收和社保证据同时存在。
- 修复后已迁移真实数据库并重启服务。
- 已对真实标书 `id=15` 重新匹配：
  - `matched=0`
  - `unmatched=0`
  - `needs_review=2`

#### 验证

- `backend/.venv/Scripts/python.exe test_match_without_raganything.py`：通过。
- `PYTHONIOENCODING=utf-8 backend/.venv/Scripts/python.exe test_smoke.py`：通过。
- `frontend npm run build`：通过，仅保留既有 chunk-size 警告。
- 真实接口验证：
  - `POST /api/v1/match/15` 完成。
  - `GET /api/v1/match/15/status` 返回 `completed`，2 条均为 `needs_review`。
  - `GET /api/v1/match/corrections?limit=20` 返回正常，目前无人工纠错记录。

### 2026-06-30：匹配链路、资质库和交互收口 ✅

#### 资质库与文件处理

- 资质库页完成三张核心表统一体验：
  - 标书核对结果表、资质库已上传文件表、资质列表均统一为每页 10 条。
  - 文件列表和资质列表均支持批量选择、批量删除。
  - 资质上传解析完成后自动清空待上传队列，避免用户切换分类后重复上传。
- 资质列表按分类/类型动态表头：
  - 企业资质、财务、人员资质分别使用贴合业务的列名。
  - 人员资质再细分为身份证明、社保证明、职称/资格证明、特种作业证、其他人员证明。
  - 财务明细已适配纳税证明、完税证明、财务会计报告等口径。
- 所有资质库文件新增网页查看能力：
  - 后端新增知识库文件预览接口。
  - 前端支持 PDF/图片在页面内预览，其他文件可新窗口打开/下载。

#### 业绩库

- 业绩从普通资质中拆出，作为独立“业绩项目”管理。
- 上传业绩证明文件入口收口为一个按钮，固定归入 `performance` 分类。
- 业绩文件解析走本地提取 + 业绩项目同步，不依赖 LLM 主路径。
- 当前真实业绩文件 `业绩表2026年.pdf` 已同步生成 8 条业绩项目，无未关联业绩文件。

#### 匹配引擎

- 匹配范围收口为“能由资质库证明的能力项”：
  - 允许进入匹配：企业资质、业绩、财务、人员资质。
  - 不进入资质库匹配：独立承担民事责任、履约能力声明、无重大违法、信用中国、非公益一类、关联关系、报价/最高限价、违约赔偿、人员不可兼任等承诺/规则类条款。
- 匹配策略恢复为“规则主判 + LLM 兜底”：
  - 本地字段、关键词、同义词、数值规则先判断。
  - 低置信度项调用 LLM 复核。
  - LLM API 失败时标记为需人工确认，不应阻塞整体流程。
- 当前真实标书重新匹配后，资质匹配项从 18 条收口为 7 条：
  - 良好商业信誉和健全财务制度
  - 依法纳税和社保
  - 类似项目业绩要求
  - 项目经理等技术负责人持证要求（评分项）
  - 项目经理等技术负责人职称要求（评分项）
  - 管理体系认证（评分项）
  - 类似业绩（评分项）

#### 匹配页面与核对页交互

- 核对页点击“与资质库匹配”后：
  - 后端返回实时进度。
  - 前端显示进度条、当前要求、已匹配/不匹配/待确认计数。
  - 匹配完成后自动跳转到 `/match` 汇总页。
- `/match` 改为匹配结果汇总表：
  - 每行对应一份标书。
  - 显示总匹配项、通过、不通过、待确认、最近匹配时间。
  - 支持刷新汇总、重新分析、开始分析。
  - 点击匹配数字或“查看明细”进入对应标书明细。
- `/match/:id` 改为右侧覆盖式抽屉明细：
  - 不再显示“选择标书”卡片。
  - 不挤压左侧页面空间，仅遮罩覆盖。
  - 左上角返回图标按钮返回 `/match`。
  - 点击抽屉外遮罩也等同返回。
  - 明细中保留企业资质匹配、技术响应表、投标待办清单和证据查看。

#### 验证

- 后端测试：
  - `backend/test_reclassification.py`：81/81 通过。
  - `backend/test_match_without_raganything.py`：通过。
  - `backend/test_match_trigger.py`：通过。
  - `backend/test_performance_project_parsing.py`：通过。
  - `backend/test_knowledge_field_normalization.py`：通过。
- 前端验证：
  - TypeScript `tsc -b` 通过。
  - Vite 生产构建通过，仅保留既有 chunk-size 警告。
  - 浏览器实测 `/match` 汇总页、`/match/14` 抽屉明细、遮罩点击返回、证据查看入口正常。
- 服务清理：
  - 用户切换其他项目，已停止本项目后端 8000、前端 5173 和 esbuild 辅助进程。
  - 端口 8000/5173 均确认未监听。

### 2026-06-24（长文档解析卡死修复）

#### 长文本分块死循环修复 ✅

- **现象**：解析 148 页标书时电脑卡死，任务长期停留在 `extracting`
- **根因**：长文本最后一段到达文末后仍执行 `start = end - overlap`，游标固定在文末前 2000 字符，循环无限追加尾段并耗尽内存
- **修复**：
  1. 新增 `app/utils/text_chunks.py` 安全分块工具
  2. 到达文末立即退出，保证游标有限前进
  3. 增加参数校验和 500 段安全上限
  4. 新增 `backend/test_tender_chunking.py`，覆盖边界文本、长文本、重叠和异常分块数量
- **验证**：
  - 4 项分块回归测试通过
  - 真实 148 页样本共 82,056 字符，稳定分为 4 段
  - Python 编译检查通过
  - 后端烟雾测试因应用重型依赖加载超过 4 分钟未完成，未计为通过

#### 标书要求详情页信息层级优化 ✅

- 将 96 条要求的平铺长表改为“统计概览 + 快速筛选 + 分类折叠 + 条目展开”
- 顶部新增全部/硬性/数值/需核对四项统计
- 新增分类、关键词、只看硬性、只看数值要求筛选
- 资质/业绩/财务/人员/其他按固定顺序折叠，默认展开资质
- 要求条目默认显示摘要，点击后展开完整要求和原始文本
- “开始匹配”移动到详情标题栏，无需滚动到底部
- 验证：
  - 4 项纯函数回归测试通过
  - TypeScript 编译通过
  - Vite 生产构建通过
  - 真实 96 条要求浏览器实测通过，控制台 0 个应用错误

#### 标书解析核对工作台重构 ✅

- 将分类折叠列表进一步重构为左右分栏 Master-Detail 工作台
- 左侧改为紧凑单行表格，桌面视口可直接查看约 16 条要求
- 修复前后端页码字段映射错误：后端 `page_number/raw_text` 正确映射到前端
- 右侧嵌入原始 PDF，点击左侧要求自动跳转到对应页
- PDF 顶部同步高亮展示该要求的原始文本片段
- 新增解析核对状态：待确认 / 已确认 / 页码定位失败
- 默认按页码定位失败 → 待确认 → 已确认排序
- 新增单条确认、行内编辑、单条删除、批量确认、批量删除和手动新增要求
- 数据库新增 `tender_requirements.review_status`
- 新增要求编辑/删除/批量操作/PDF 文件流 API
- 验证：
  - 后端 2 项核对能力测试通过
  - 前端 3 项字段映射与排序筛选测试通过
  - TypeScript 编译与 Vite 生产构建通过
  - 真实 96 条要求浏览器验证通过，PDF 可跳转至第 3/29 页
  - 浏览器控制台 0 个应用错误

#### 核对页面独立路由 + 显式匹配流程 ✅

- 新增独立核对页面 `/tenders/{id}/review`
- 标书解析页恢复为单一职责：上传、列表、解析状态和“核对结果”入口
- 核对页显示确认进度，并保留左右分栏 PDF 核对工作台
- 存在未确认要求时，开始匹配前给出提示，可返回继续核对或强制继续
- 核对页提交匹配后跳转 `/match/{id}` 等待结果
- 匹配页取消“选择标书后自动触发匹配”
- 匹配页进入时只读取已有结果
- 无结果时显示“尚未匹配”和“开始匹配”按钮
- 有结果时显示“重新匹配”按钮
- 浏览器网络验证：直接访问 `/match/10` 仅发送 GET，请求中无 POST 匹配调用

### 2026-06-22（项目启动 + MVP 交付）

#### Phase 0：沟通与需求确认

- **13:20** — 用户提出基于 RAG-Anything 二开标书分析系统的想法
- **13:30** — 完成 API 选型调研：
  - LLM → DeepSeek（用户已有 Key）
  - Embedding → 硅基流动 BAAI/bge-m3（待申请）
  - Vision → 硅基流动 nex-agi/Nex-N2-Pro（限免模型，⚠️ 风险：可能转收费、可能不支持 `image_url`）
- **13:45** — 确认 OCR 方案：MinerU 已内置 PaddleOCR，不需要单独集成
- **14:00** — 用户回答 PRD 10 问，确定关键决策：
  - 模板格式：DOCX/PDF/XLSX 多格式
  - 知识库：全格式（含扫描件 OCR）
  - 不符合项要详细：具体不符合点 + 期望资质 + 是否已上传
  - UI 配色：淡紫色 `#7C4DFF` + 白色（不要深色主题）
  - 自动填写输出：DOCX + PDF 双输出
  - 资质字段：7 项（证书名称/编号/有效期/发证机构/认证范围/等级/持证主体）
  - 规则校验：5 类数值（注册资本/合同金额/营业收入/资产负债率/人员年限）
- **14:30** — 用户明确：API Key 只在前端 UI 填写，不写配置文件（数据安全顾虑）

#### Phase 1：环境搭建 ✅

- **14:00** — LibreOffice 26.2 安装完成，加入系统 PATH
- **14:15** — Python venv 创建完成
- **14:20** — 真实标书 `JSZC-320508-JDJS-G2026-0002采购文件.doc` 用 LibreOffice 转 PDF 成功（3.5MB）

#### Phase 2：RAG-Anything 技术验证 ✅

- **14:30** — 安装 raganything 1.3.1 + lightrag-hku 1.5.3 + mineru 3.4.0 + paddleocr 3.7.0 + paddlepaddle 3.3.1
- **14:45** — 验证 RAG-Anything API 全部可用：`process_document_complete`、`aquery`、`aquery_vlm_enhanced`、`insert_content_list`
- **15:00** — ⚠️ 遗留 3 个阻塞点：
  1. API Key 未填（用户坚持只在前端填，所以跳过实际解析验证）
  2. torch 2.12.1 有 `shm.dll` 加载问题（WinError 127），但不影响 paddleocr
  3. Nex-N2-Pro 视觉支持未验证（需 API Key 实测）
- **15:00** — 决定：跳过实际解析验证，直接进入架构设计

#### Phase 3：PRD + 架构设计 ✅

- **14:50** — 产品经理许清楚完成 `docs/PRD.md` v1.1（11 P0 + 7 P1 + 4 P2 需求）
- **15:00** — 架构师高见远完成 `docs/ARCHITECTURE.md`（904 行）+ 类图 + 时序图
- **15:00** — 任务分解：T01（骨架）→ T02（数据层+API配置）→ T03（后端核心业务）→ T04（前端）→ T05（联调）

#### Phase 4：代码开发 ✅

- **15:11** — 工程师寇豆码启动 T01 + T02 开发
- **15:30** — T01 + T02 完成（27 个 Python 文件），但因 429 限流中断，主理人手动验证 5 个 API 端点全部可用
- **15:40** — T03 后端核心业务完成（10 个新文件 + 2 个更新），21 个路由全部可用
- **15:40** — T04 前端开发因 429 限流中断，完成 30/35 个文件，缺 5 个页面文件
- **15:55** — 工程师补完前端 5 个页面（Dashboard/Tender/Knowledge/Match/Settings），`npx tsc -b` 零错误，`npm run build` 成功

#### Phase 5：集成联调 ✅

- **15:55** — 主理人手动完成 T05：
  - 验证后端 21 个路由全部可用
  - 验证前端 38 个文件编译通过
  - 更新 `start.bat`：默认打开前端页面（localhost:5173）而非 API 文档
  - 添加首次使用提示：先在设置页配置 API Key

#### 启动报错修复 ✅

- **16:20** — 用户报告启动报错：`[WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试`
- **16:20** — 诊断：端口 8000 被残留的 uvicorn 进程（PID 1504）占用
- **16:21** — 修复：终止残留进程 + 改进 `start.bat` 自动清理占用 8000/5173 端口的残留进程
- **16:22** — 验证：后端 + 前端均成功启动，健康检查通过

#### 文档补充 ✅

- **16:25** — 补充 README.md / PROGRESS.md / docs/DELIVERY.md
- **16:25** — 优化 PROJECT_PLAN.md / phase2_validation/README.md，移除特定 AI 工具路径，统一为相对路径
- **16:33** — 创建 `AI_HANDOVER.md`（项目唯一的 AI 交接入口文档）

#### API 配置弹窗白屏 Bug 修复 ✅

- **16:36** — 用户报告：点击 API 配置界面全屏白屏
- **报错**：`ApiConfigDialog.tsx:272 Uncaught TypeError: presets.map is not a function`
- **根因**：前后端数据格式不匹配
  - 后端 `/config/presets` 返回**嵌套对象**：`{presets: {deepseek: {llm: {...}}, siliconflow: {...}, ...}}`
  - 前端期望**扁平数组**：`ConfigPreset[]`
  - axios 拦截器 unwrap 后，`presets` 是对象，调用 `.map()` 崩溃
- **修复**（3 个文件）：
  1. `frontend/src/types/index.ts` — `ConfigPreset` 接口新增 `config_type` 字段
  2. `frontend/src/api/config.ts` — `getPresets()` 增加格式转换逻辑，把后端嵌套对象转成扁平数组；加防御性处理（格式异常时返回空数组）
  3. `frontend/src/components/ApiConfigDialog.tsx` — 预设查找/渲染改为按 `provider + config_type` 双重过滤
- **验证**：
  - `npx tsc -b` 零错误 ✅
  - Vite HMR 热更新成功 ✅
  - 后端 API 返回正常 ✅
- **附带说明**：`fatkun-vip.js` 的 404 报错是浏览器扩展（Fatkun 批量下载）引起，与项目无关

#### API 配置弹窗重构：支持跨 provider 多模型配置 ✅

- **背景**：弹窗 Copy 自旧项目，是「1 Base URL + 1 API Key + 3 模型下拉」的统一结构，只适合三类模型同一 provider。但用户计划 LLM 用 DeepSeek、向量+视觉用千问，三者来自不同 provider、需要各自独立的 URL/Key，旧弹窗无法表达。
- **关键发现**：后端 `api_configs` 表本就是按 `config_type` 分行存储（各自独立 base_url + api_key + model_name），`/config/test` 也按单类独立测 —— **后端天然支持，0 改动**。问题纯在前端。
- **改动**（4 个前端文件，后端零改动）：
  1. `frontend/src/types/index.ts` — `ApiConfigInput` 加可选 `id` 字段
  2. `frontend/src/api/config.ts` — 新增 `getConfigsByType(type)` 辅助函数（按 config_type 筛活跃配置）
  3. `frontend/src/components/ApiConfigDialog.tsx` — **重写主体**：三类模型（LLM 蓝/向量 紫/视觉 红）各自独立子卡片，每块各有自己的 Base URL + API Key + 模型名 + 独立「测试连接」；保存时对填了 Base URL 的类分别 `saveConfig`；编辑模式拉全量按 config_type 回填；模型名改文本输入（手填为主）
  4. `frontend/src/pages/SettingsPage.tsx` — 配置列表从「按 provider 分组」改为「按 config_type 分三类」，每类一张卡片
- **验证**：`npx tsc -b` 零错误 ✅；`npm run build` 成功（1033 模块，556KB JS，2.7s）✅
- **数据安全**：明文 Key 不回填、SQLite 加密存储 + 返回脱敏、日志 `[REDACTED]`，主密钥来自 `RAG_TENDER_SECRET_KEY`
- **旧数据兼容**：之前用旧弹窗存的配置（三类同 provider）在新弹窗编辑时能正确回填（按 config_type 取），不丢数据

#### start.bat 启动脚本修复（乱码 + npm 找不到）✅

- **背景**：用户双击 `start.bat` 报中文乱码 + 前端窗口 `npm 不是内部或外部命令`
- **乱码根因**：`start.bat` 是 UTF-8 无 BOM 编码，中文 Windows cmd（代码页 936/GBK）读取时把中文当 GBK 解释 → 乱码
- **npm 找不到根因**：`start "标题" cmd /k "cd /d "路径" && npm"` 多层引号嵌套，cmd 解析时把 `&& npm` 切断，且项目路径含空格（`RAG-Tender Assistant`）导致 cd 失败
- **修复**（后端零改动）：
  1. 所有 .bat 改为 **GBK 编码**存储（中文 Windows 原生编码，不依赖 chcp）
  2. 拆成独立启动脚本：
     - `start.bat` — 主启动器（端口清理 + 调用下面两个 + 开浏览器）
     - `_start_backend.bat` — 后端独立启动（`cd /d "%~dp0backend"` + python run.py）
     - `_start_frontend.bat` — 前端独立启动（`cd /d "%~dp0frontend"` + `call npm run dev`）
  3. 子脚本用 `chcp 65001` 保证输出窗口中文正确
  4. 前端脚本额外 `set PATH=%PATH%;C:\Program Files\nodejs` 兜底
- **验证**：
  - 后端 `/config/presets` 健康检查通过（HTTP 200）✅
  - 前端 `_start_frontend.bat` 日志确认 cd 正确 + Vite 392ms 启动成功 ✅
  - Python 环境：`C:\Users\DELL\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（3.13.12, raganything OK）✅

---

### 2026-06-23（持续迭代 — 文档解析重构 + UI 优化 + 搜索筛选）

#### 文档解析彻底重构

- 移除 RAG-Anything/mineru 3.x 依赖（在 Intel UHD 730 128MB VRAM 上无法运行）
- 参考 industrial-marketing-ai 项目的成熟方案，新建 `document_parser.py`
- PyPDF2 直接提取文本（148 页 10 秒），扫描页 Vision API OCR 兜底
- `parse_tender()` 彻底重写，30 秒完成（之前 15 分钟+失败）
- 安装 docling/pypdf/PyPDF2/pdf2image 等依赖

#### LLM 提权提示词优化

- 系统提示词从 300 字扩展到 1900 字，穷举 50+ 种子类目
- 长文本分段提取：每段 25000 字符 + 重叠 2000 字符，去重合并
- max_tokens 从 4000 提升到 8000

#### API 配置功能完善

- 弹窗打开默认回填已保存配置
- 卡片测试连接自动从 DB 取 Key（三级回填）
- mineru CLI PATH monkey-patch（`rag_service.py`）

#### 设置页 API 配置卡片重设计

- 三张独立卡片合并为紧凑单卡片，按 base_url 分组
- 去阴影、去圆角、去紫色背景，扁平直角边框
- 地区筛选改为省份下拉选择器（4 列网格布局）
- 每个卡片独立显示各自测试结果

#### 标书解析页面优化

- 搜索框 + 状态下拉 + 省份选择器（4 列网格）
- 表格增加地区列、删除按钮（含确认弹窗）
- DB 增加 region/procurement_type/budget/agency 四列
- LLM 同步提取元数据（地区/采购方式/预算/采购单位）

#### 标书详情页重构

- 5 个分类标签（资质/业绩/财务/人员/其他）合并为一张表格
- 去掉 RequirementCard 折叠卡片，改为扁平表格直接展示
- 分类 chip + 硬性/普通标签 + 完整要求文字 + 数值要求列

#### UI 整体去阴影去圆角

- TenderPage/SettingsPage 全部 Paper→Box+border
- 所有面板 borderRadius=0 扁平直角风格

---

## ✅ 已完成清单

### 后端（31 个 Python 文件 → 新增 `document_parser.py`）

- [x] 项目骨架（`run.py` / `main.py` / `config.py` / `database.py`）
- [x] 7 张数据表 + 4 个扩展列（region/procurement_type/budget/agency）
- [x] 5 套 Pydantic schema
- [x] 22 个 API 端点（config / tenders / knowledge / match / fill / debug）
- [x] 7 个业务 service（rag / tender / knowledge / match / fill / file_convert / document_parser）
- [x] 智能文档解析：PyPDF2 文本提取 + Vision OCR 兜底
- [x] 穷举式 LLM 提权提示词 + 长文本分段提取
- [x] API Key 安全机制（SQLite 加密存储 + API 返回脱敏 + 日志 [REDACTED]）
- [x] 5 类数值规则匹配引擎
- [x] 3 层不符合信息
- [x] DOCX/XLSX/PDF 模板填写

### 前端（38 个文件）

- [x] 配置文件（package.json / vite.config.ts / tsconfig / tailwind / postcss / index.html）
- [x] 入口文件（main.tsx / App.tsx / theme.ts / index.css）
- [x] API 调用层 6 个文件（client / config / tenders / knowledge / match / fill）
- [x] 7 个组件（Layout / Sidebar / ApiConfigDialog / FileUploader / RequirementCard / MatchResultTable / StatusBadge）
- [x] 5 个页面（Dashboard / Tender / Knowledge / Match / Settings）
- [x] TypeScript 类型定义
- [x] React hooks（useApi）
- [x] 淡紫色主题（#7C4DFF）
- [x] `npx tsc -b` 零错误
- [x] `npm run build` 成功（1027 模块，518KB JS）

### 文档

- [x] `README.md`（项目入口）
- [x] `PROJECT_PLAN.md`（项目背景与技术方案）
- [x] `PROGRESS.md`（本文件）
- [x] `docs/PRD.md` v1.1
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/DELIVERY.md`
- [x] `docs/class-diagram.mermaid`
- [x] `docs/sequence-diagram.mermaid`
- [x] `phase2_validation/README.md`

### 工具与脚本

- [x] `start.bat`（一键启动，含端口清理，GBK 编码）
- [x] `_start_backend.bat`（后端独立启动脚本）
- [x] `_start_frontend.bat`（前端独立启动脚本）
- [x] `.gitignore`
- [x] `backend/requirements.txt`
- [x] `backend/test_smoke.py`

### 样本文件

- [x] 真实标书 `JSZC-320508-JDJS-G2026-0002采购文件.doc`（173KB，用户提供）
- [x] 真实标书 PDF（3.5MB，已转换）
- [x] 生成样本 `控制柜配电柜变频柜采购招标公告_样本.pdf`（852KB）

---

## ❌ 遗留问题与待办

### 🔴 高优先级

| # | 问题 | 影响 | 建议处理 |
|:---:|:---|:---|:---|
| 1 | **PDF 模板填写仍会丢格式** | PDF 模板导出会损失原始版式，影响最终投标文件可直接交付性 | 优先评估更稳妥的 PDF 回填/定位方案 |
| 2 | **规则库归并接口未闭环** | `PUT /api/v1/rules/{rule_id}/merge` 已暴露但服务层缺少实现，相关 API 测试失败 | 在 `rule_library_service.py` 实现 `merge_custom_rule`，再补回归测试 |
| 3 | **真实业务数据仍需持续复盘** | 当前保守判定与红线规则已收口，但样本量不足时仍可能过严或漏判 | 用更多真实标书、资质库样本复核严格度和规则覆盖 |

### 🟡 中优先级

| # | 问题 | 建议 |
|:---:|:---|:---|
| 4 | 长时任务无进度反馈 | 继续补充更细粒度的解析/匹配/填写进度提示 |
| 5 | 投标待办红线规则仍需扩展 | 继续补授权书、报价日期、暗标敏感信息等更细检查项 |
| 6 | 规则库仍需持续补齐 | 继续沉淀资质类型、人员证书、业绩细则、地区政策等规则 |
| 7 | 资质结构化字段仍需增强 | 补齐有效期、等级、适用范围、证据页等更细字段 |

### 🟢 低优先级（增强项）

| # | 问题 | 建议 |
|:---:|:---|:---|
| 8 | 历史标书对比（PRD P2-04） | 暂不做，用户明确说"暂不要" |
| 9 | 深色模式（PRD P2-03） | 已删除，用户明确拒绝 |
| 10 | 批量标书处理 | 当前一次一份，未来可扩展 |

---

## 🔑 关键技术决策（防止反复讨论）

| 决策点 | 选择 | 理由 | 不要再改 |
|:---|:---|:---|:---|
| 数据库 | SQLite（不是 PostgreSQL） | 本地单机，零配置 | ✅ |
| 前端框架 | React 18 + MUI（不是 Vue） | 生态成熟 | ✅ |
| 主题 | 淡紫色 + 白色（不要深色） | 用户明确要求 | ✅ |
| API Key 存储 | SQLite 密文 + API 返回脱敏 + 环境变量主密钥 | 适合本地自部署与开源分发 | ✅ |
| API Key 配置入口 | 前端 UI 弹窗（不是 config.yaml） | 用户数据安全顾虑 | ✅ |
| 文档解析 | PyPDF2 + python-docx 直接提取（不是 mineru） | 用户显卡不支持 VLM，纯文本方案 30 秒完成 | ✅ |
| Embedding 模型 | BAAI/bge-m3（维度 1024，不是 GLM-Z1-9B） | GLM-Z1-9B 是 LLM 不是 Embedding | ✅ |
| Office→PDF | LibreOffice headless | 已装、稳定 | ✅ |
| 模板占位符 | Mustache 风格 `{{字段名}}` | 简单直观 | ✅ |
| 长时任务 | FastAPI BackgroundTask + 前端轮询 | 简单够用 | ✅ |

---

## 📞 用户偏好（接手者必读）

1. **沟通风格**：用户喜欢直接、不绕弯子的回答；不喜欢冗长解释
2. **数据安全**：用户对 API Key 极度敏感，**绝不能**把 Key 写到任何配置文件或日志
3. **路径**：所有项目文件必须放在 `D:\projects\RAG-Tender Assistant\`
4. **测试数据**：用 `JSZC-320508-JDJS-G2026-0002采购文件.doc` 作为真实测试标书
5. **配色**：淡紫色 `#7C4DFF` + 白色，不要提议深色主题
6. **部署**：本地 Windows 单机，不要提议云部署
7. **使用者**：单人自用，不要提议多用户/权限系统

---

## 📝 维护说明

- **追加规则**：每完成一个阶段或解决一个重要问题，在本文件「进度时间线」追加一条
- **不修改历史**：已发生的事不删改，新进展追加在新条目
- **状态同步**：「当前状态」表格随项目进展实时更新
- **遗留问题闭环**：解决的问题从「遗留问题」移到「已完成清单」，并在时间线记录

---

### 2026-06-25：标书要求分类改造完成 ✅

#### 问题发现：标书解析分类粒度不合理

- **现象**：用户实测发现，解析出的部分"资质"项实际不属于企业资质范畴：
  - 设备参数要求（如"输出功率≥200kW"）被归到 `qualification`，拿去知识库匹配营业执照/ISO，永远 unmatched
  - 提交件要求（如"提交法人授权委托书"、"提交资格承诺书"）被归到 `qualification` 或 `other`，匹配企业资质无意义
- **根因定位**（代码层）：
  - `backend/app/services/tender_service.py` 第 62-70 行 `_EXTRACT_SYSTEM_PROMPT`：`qualification` 类明确列了"设备证明、检测报告、制造商授权书"
  - 同文件第 95-104 行 `other` 类兜底"任何投标人须知/资格性审查章节下的任何条件"
  - `backend/app/services/match_service.py` `match_tender()`：对 5 类一视同仁走"找企业资质"流程，无分流
- **本质**：当前 5 类分类只区分"主题"（关于什么），没区分"处理动作"（拿到后该干嘛）

#### 改造方向（已与用户对齐）

- **按处理动作拆三类**：企业资质类（保留）/ 产品技术参数类（新增）/ 投标待办提交件类（新增）
- **业绩/财务/人员三类内部区分子维度**：`capability`（能力要求，走匹配）vs `submission`（提交材料，走待办清单）
- **产品检测报告**：参数要求归产品类，"提供报告"动作归待办类
- **改造范围**：彻底改（后端 prompt/枚举/分流/新service + 数据库 + 前端新页面）
- **方案文档**：`docs/REQUIREMENT_RECLASSIFICATION_PLAN.md`（本次改造的"宪法"）

#### 工作流：标准 SOP（进行中）

- [x] 主理人整理方案文档 `docs/REQUIREMENT_RECLASSIFICATION_PLAN.md`
- [x] 同步 PROGRESS.md / AI_HANDOVER.md
- [x] TeamCreate 建立 `software-req-reclass` 团队
- [x] 产品经理许清楚 → 增量 PRD（已落盘 `docs/PRD_INCREMENTAL_RECLASSIFICATION.md`，4 P0 + 4 P1 + 4 P2）
- [x] 用户确认 PRD 中 3 个待决问题（Q1 历史重解析/Q4 截止时间字段/Q5 灰色地带处理）
- [x] 架构师高见远 → 增量设计 + 任务分解（已落盘 `docs/ARCHITECTURE_INCREMENTAL_RECLASSIFICATION.md`，704 行；5 任务 T01-T05 / 27 文件；含完整 prompt 草稿 + 3 时序图 + 类图）
- [x] 主理人对架构师 7 个待明确事项全部采纳决策
- [x] 工程师寇豆码 → 批量实现 T01-T05（29 文件：13 新建 + 16 修改；IS_PASS: YES；后端 import OK + 前端 tsc 零错误）
- [x] QA 严过关 → 测试验证（79 项全通过，路由判定 NoOne；测试文件 `backend/test_reclassification.py`）
- [x] 主理人 → 同步最终文档 + 交付汇总

#### 交付成果

- **代码**：29 文件改动（13 新建 + 16 修改），后端 16 + 前端 13
- **数据库**：tender_requirements 加 requirement_nature 列；新建 technical_responses 表；新建 submission_checklist 表
- **匹配分流**：`_should_match()` 函数——product_spec 跳过、submission nature 跳过、只 capability 走匹配
- **新 Prompt**：三类分类 + nature 子维度 + 拆条规则 + 3 个 few-shot 示例
- **新前端页面**：三 Tab 布局（企业资质匹配/技术响应表/投标待办清单）
- **测试**：79 项全通过，覆盖匹配分流/数据库迁移/Service CRUD/Prompt 格式/回归
- **文档**：方案文档 + 增量 PRD + 增量架构设计 + PROGRESS/AI_HANDOVER 同步

---

### 2026-06-24：核对工作台改为显式匹配 + PDF 抽屉

- 核对结果页默认使用全宽紧凑表格，不再常驻显示 PDF 阅读器。
- 用户手动点击“与资质库匹配”后，页面停留在当前工作台并轮询结果。
- 匹配完成后原表追加“我的资质”“匹配状态”列，不匹配和待人工核对项优先展示。
- 点击条目或原文页码后，右侧抽屉按需加载 PDF 并跳转到对应页。
- 新增匹配结果字段归一化，兼容后端 `status` 与前端 `match_status`。
- 新一轮匹配提交前同步清除旧结果，避免轮询误读上一次数据。
- 修改、新增、删除解析要求后清空过期匹配展示；仅确认解析状态不会使匹配失效。
- 验证结果：前端 6 项单元测试通过，TypeScript 编译和 Vite 构建通过；后端 7 项专项测试及 10 项隔离烟雾测试通过。

### 2026-06-24：前端“知识库”文案统一改为“资质库” ✅

- **背景**：用户在 UI 上看到侧边栏“知识库”菜单项和“与知识库资质匹配”按钮，要求把面向用户的“知识库”统一改成“资质库”，更贴合该模块实际承载的资质文件语义。
- **改动范围**：5 个前端文件共 9 处面向用户的中文文案，技术标识（路由 / 组件名 / 类型 / API 字段 / 模块路径 / 图标）零改动。
  - `frontend/src/components/Sidebar.tsx:27` — 侧边栏菜单 label「知识库」→「资质库」
  - `frontend/src/pages/Dashboard.tsx:57` — 快捷卡片标题「知识库管理」→「资质库管理」
  - `frontend/src/pages/KnowledgePage.tsx:359` — 空状态提示「请上传知识库文件」→「请上传资质库文件」
  - `frontend/src/components/MatchResultTable.tsx:159` — 未找到提示「知识库未找到」→「资质库未找到」
  - `frontend/src/components/MatchResultTable.tsx:305` — 第三层小标题「知识库检查」→「资质库检查」
  - `frontend/src/components/RequirementReviewWorkbench.tsx:385,387,460,654` — 按钮 / Alert / 兜底文案
- **去重处理**：「知识库资质」连用直接替换会变成「资质库资质」（重复），故 3 处去重：
  - 「与知识库资质匹配」→「与资质库匹配」
  - 「重新匹配知识库资质」→「重新匹配资质库」
  - 「正在逐项与知识库资质匹配…」→「正在逐项与资质库匹配…」
- **保留未改**：路由 `/knowledge`、组件 `KnowledgePage`、类型 `KnowledgeFile`/`KnowledgeCategory`、API 字段 `in_knowledge_base`、模块 `../api/knowledge`、图标 `LibraryBooksIcon` —— 这些是技术约定，改动会破坏前后端契约。
- **验证**：QA 独立复核 9/9 通过；`tsc --noEmit` EXIT_CODE=0；`知识库` 全量搜索（frontend/src）无残留。
- **遗留说明**：MatchResultTable.tsx 第 305 行文案「资质库检查」与同区块 308/310 行后端字段 `in_knowledge_base` 并存——仅前端文案改，后端字段名未动，前后端约定无破坏。如后续希望英文注释 / 组件名 / 路由也统一为 qualification，需另行立项重构。

### 2026-06-25：Windows 重启后 DOC 标书直接解析失败修复 ✅

- **现象**：重启项目并重新上传真实 `.doc` 标书后，状态立即变为“失败”，无 PDF 路径、页数为 0。
- **根因 1**：Uvicorn 0.49 在 Windows 热重载模式下使用不支持异步子进程的事件循环，`asyncio.create_subprocess_exec()` 调用 LibreOffice 时抛出 `NotImplementedError`。
- **根因 2**：旧 Uvicorn reload worker 长期占用 8000 端口，`start.bat` 重启后新后端未实际接管端口，浏览器仍访问旧代码。
- **修复**：
  1. `file_convert.py` 改为 `asyncio.to_thread(subprocess.run)` 执行 LibreOffice，兼容 Windows SelectorEventLoop。
  2. `run.py` 关闭 Uvicorn 热重载，改为单进程运行，避免残留 worker 和端口归属异常。
  3. 新增 `backend/test_file_convert.py` 回归测试。
  4. `test_smoke.py` 改用临时 SQLite，避免烟雾测试覆盖用户真实 API 配置。
- **验证**：
  - Windows SelectorEventLoop 下真实 LibreOffice 转换成功，PDF 148 页。
  - 分类改造专项测试 79/79 通过。
  - 隔离烟雾测试 10/10 通过。
  - 正式 8000 端口端到端解析完成：148 页，提取 70 条要求。

### 2026-06-25：标书核对工作台分页 + 性质筛选 ✅

- 核对结果表改为每页 20 条，取消固定高度和表格内部滚动条。
- 底部新增分页、当前范围和总数，例如“21–40 / 共 70 项”。
- 顶部快捷按钮从“待确认/页码定位失败/已确认”改为“全部/能力要求/提交资料”。
- 解析状态继续在表格“解析状态”列展示；匹配状态继续在匹配状态列展示。
- 删除重复的“全部性质”下拉框，保留关键词搜索和类别下拉。
- 全选只作用于当前页，跨页已选项继续保留；序号跨页连续。
- 筛选变化自动返回第 1 页，数据减少时自动校正到最后有效页。
- 验证：
  - 前端纯函数测试 9/9 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过。
  - 真实 70 条要求浏览器验证：第一页 20 条、第二页从 21 开始、提交资料 22 条分 2 页。
  - 表格无横向/纵向内部滚动条，浏览器控制台 0 错误。

### 2026-06-25：三张表统一每页 10 条 ✅

- 新增通用分页工具 `frontend/src/utils/pagination.ts`，统一处理分页切片和越界页码校正。
- 标书核对结果从每页 20 条调整为每页 10 条。
- 资质库“已上传文件”新增每页 10 条分页。
- 资质列表新增每页 10 条分页，分类切换自动回到第 1 页。
- 文件列表与资质列表维护独立页码，切换 Tab 时互不影响。
- 三张表统一显示当前范围和总数，且均不使用内部滚动条。
- 验证：
  - 通用分页与核对纯函数测试 11/11 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过。
  - 浏览器实测：核对结果 1–10/70、上传文件 1–10/78、资质列表 1–10/66。
  - 三张表均无内部纵向滚动条，浏览器控制台 0 错误。

### 2026-06-26：资质列表按分类动态表头 ✅

- 资质库页“资质列表”移除“全部分类”，默认进入“企业资质”。
- 表格表头按当前分类切换，避免财务、人员、业绩资料套用企业证书字段。
- 当前映射：
  - 企业资质：名称、编号、发证日期、有效期至、发证机构、认证范围、等级、持证主体。
  - 人员资质：人员/证书名称、证书编号、发证日期、有效期至、发证机构、专业/范围、等级、持有人。
  - 业绩：项目/业绩名称、合同/项目编号、签订/开始日期、完成/有效期、业主/发包方、项目范围、金额/等级、主体。
  - 财务：资料名称、年度/编号、出具日期、覆盖期/有效期、出具机构、指标/范围、结论/等级、主体。
  - 其他：名称、编号、日期、有效期、来源/机构、内容摘要、等级/类型、主体。
- 保持后端资质字段和数据库不变，仅调整前端展示语义。

### 2026-06-26：移除顶部栏并隐藏 API 配置入口 ✅

- 全局布局移除顶部 `AppBar/Toolbar`，页面内容直接上移到内容区顶部，不再被无意义标题栏占用空间。
- 删除顶部可见的 `RAG-Tender Assistant` 标题和“API 配置”文字按钮。
- API 配置入口改为右上角 56×56 固定热区，默认齿轮按钮透明隐藏。
- 鼠标进入热区或键盘聚焦时显示齿轮，点击仍打开原 `ApiConfigDialog`。
- 验证：
  - 新增布局热区测试，前端测试 19/19 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：`AppBar/Toolbar` 为 0，`mainTop=0`，右上角坐标点击可打开 API 配置弹窗，控制台 0 错误。

### 2026-06-26：资质列表批量改分类 + 源文件级批量删除 ✅

- 资质列表新增多选列，支持当前页全选/取消全选。
- 选中资质后显示批量操作栏：
  - 批量改分类：更新选中资质 `qualifications.category`，并同步更新关联 `knowledge_files.category`，避免重新解析后分类回退。
  - 批量删除：按源文件级删除，有 `file_id` 的资质会删除对应源文件、该文件解析出的全部资质记录和物理文件；无 `file_id` 的手动资质只删除该条记录。
- 批量删除前弹出确认框，明确显示将删除的源文件数量和手动资质数量，避免误删。
- 后端新增接口：
  - `POST /api/v1/knowledge/qualifications/bulk-category`
  - `POST /api/v1/knowledge/qualifications/bulk-delete-source`
- 验证：
  - 后端批量服务测试通过。
  - 后端烟雾测试 10/10 通过。
  - 前端测试 23/23 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：资质列表出现选择列；选中后显示批量改分类/批量删除；两个确认弹窗正常；控制台 0 错误。

### 2026-06-26：资质库文件列表批量选择 + 批量删除 ✅

- 资质库“文件列表”新增多选列，支持当前页全选/取消全选。
- 选中文件后显示批量操作栏：
  - 显示“已选择 N 个文件”。
  - 支持“批量删除”和“取消选择”。
- 批量删除复用现有单文件删除接口，逐个删除选中文件；每个文件删除时仍会同步删除：
  - `knowledge_files` 记录
  - 关联 `qualifications` 记录
  - 本地物理文件
- 删除前弹出确认框，明确提示会删除源文件、解析出的全部资质记录和物理文件。
- 验证：
  - 新增文件选择纯函数测试，前端测试 26/26 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：文件列表出现选择列；选中后显示批量删除；确认弹窗正常；控制台 0 错误。

### 2026-06-26：资质上传解析完成后自动清空待上传队列 ✅

- 修复上传组件保留已选文件导致重复上传的问题。
- `FileUploader` 新增 `clearKey` 外部清空信号：
  - 首次渲染不清空。
  - `clearKey` 变化时清空已选文件列表、错误信息和原生 file input 值。
- 资质库页在文件解析轮询全部结束并刷新资质列表后递增 `clearKey`，自动清空上传框里的待上传文件。
- 这样企业资质上传解析完成后，切换到人员资质再上传时，不会把上一批企业资质文件带过去重复上传。
- 验证：
  - 新增 clearKey 纯函数测试，前端测试 30/30 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。

### 2026-06-26：业绩项目库一期 ✅

- 新增独立的“业绩项目库”，不再把业绩硬套普通证书资质字段。
- 后端新增 `performance_projects` 表，字段包括：
  - 项目名称、甲方/客户、合同编号、合同金额、签订日期、完成/验收日期、项目内容/供货范围、所属年度、关联文件 ID、备注。
- 后端新增接口：
  - `GET /api/v1/performance/projects`
  - `POST /api/v1/performance/projects`
  - `PUT /api/v1/performance/projects/{id}`
  - `DELETE /api/v1/performance/projects/{id}`
- 资质库页新增第三个 Tab：`业绩项目`。
- 前端支持：
  - 业绩项目列表，每页 10 条。
  - 新增/编辑/删除业绩项目。
  - 关联已上传且分类为“业绩”的证明文件。
  - 删除业绩项目不会删除源文件。
- 本期不做年度总表自动导入、不做合同 PDF 自动匹配、不改标书匹配逻辑。
- 验证：
  - 后端业绩项目 CRUD 测试通过。
  - 后端烟雾测试 10/10 通过。
  - 前端测试 32/32 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：业绩项目 Tab 存在，新增弹窗正常，控制台 0 错误。

### 2026-06-26：业绩项目库二期最小版：年度总表粘贴导入 ✅

- 业绩项目页新增“批量导入总表”入口。
- 支持从 Excel/WPS 年度总表复制带表头的表格文本后粘贴导入。
- 当前支持识别这些表头别名：
  - 项目名称/项目/业绩名称
  - 甲方/客户/建设单位/发包方
  - 合同编号/合同号
  - 合同金额/金额
  - 签订日期/合同签订日期
  - 完成日期/验收日期
  - 项目内容/供货范围/服务内容
  - 年度/所属年度
  - 备注
- 导入前会先解析并显示前 5 条预览；缺少项目名称列或无有效项目时阻止导入。
- 本期仍不做合同 PDF 自动解析和自动匹配，只解决年度总表快速入库。
- 验证：
  - 新增总表解析测试，前端测试 35/35 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：导入弹窗、粘贴解析、预览正常，控制台 0 错误；未点击确认导入，未写入真实数据。

### 2026-06-26：业绩项目库三期最小版：总表导入自动关联业绩文件 ✅

- 年度总表粘贴导入时，系统会尝试按已上传“业绩”分类文件的文件名自动关联证明文件。
- 自动关联规则：
  - 优先按合同编号匹配文件名。
  - 其次按项目名称匹配文件名。
  - 空值不参与匹配。
  - 一个项目可自动关联多个命中的文件。
- 导入预览表新增“自动关联文件”列，确认导入前可看到每条项目关联了几个文件。
- 当前仍不解析 PDF 内容，只做文件名级别的低风险自动挂接；未命中的文件仍可在编辑业绩项目时手动关联。
- 验证：
  - 新增自动关联纯函数测试，前端测试 36/36 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：导入预览显示自动关联文件数量，控制台 0 错误；未点击确认导入，未写入真实数据。

### 2026-06-26：业绩项目库四期最小版：未关联业绩文件提示 ✅

- 业绩项目页新增未关联文件提示逻辑。
- 当存在已上传“业绩”分类文件时，页面会统计：
  - 业绩文件总数。
  - 尚未关联到任何业绩项目的文件数量。
  - 最多展示前 5 个未关联文件名。
- 所有业绩文件都已关联时显示成功提示。
- 当前本地库没有“业绩”分类文件时，不显示空提示，避免页面噪音。
- 验证：
  - 新增未关联文件纯函数测试，前端测试 37/37 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：业绩项目页正常渲染，当前无业绩文件时不显示空提示，控制台 0 错误。

### 2026-06-26：资质/业绩分类入口收口 ✅

- 修正业绩项目独立后普通资质分类入口仍保留“业绩”的问题。
- 普通资质上传框的分类选项调整为：
  - 企业资质
  - 人员资质
  - 财务
- 资质列表的分类筛选、手动新增资质、批量改分类等复用同一分类源，均不再提供“业绩”选项。
- 保留历史业绩文件/记录的展示标签兼容，避免旧数据变成未知分类。
- 业绩项目页新增固定“上传业绩证明文件”入口，上传的合同、验收报告、年度证明等文件自动归入 `performance` 分类，不再混在普通资质上传下拉里。
- 验证：
  - 新增普通上传分类测试，前端测试 38/38 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器实测：业绩项目页固定上传入口存在，控制台 0 错误。

### 2026-06-26：资质文件与资质列表数量对应修复 ✅

- 定位人员资质“文件列表 8 个、资质列表只有少量记录”的根因：
  - 扫描件/图片型 PDF 使用 PyPDF2 提取文本时结果为空，后端未生成资质记录。
  - LLM 返回全空字段时，后端仍会创建一条空资质记录。
  - 文件即使没有提取出资质，也会被标记为 `completed`，前端无法看出“完成但无资质行”。
- 后端新增有效提取结果判断：
  - 全字段为空不再视为有效资质。
  - 解析失败、无文本、全字段为空时，会基于文件名生成一条“待人工补全”占位资质。
  - 占位记录的 `scope` 写明原因，例如“待人工补全：PDF 未提取到可解析文本，可能是扫描件或图片型 PDF”。
- 修复当前数据库历史数据：
  - 人员资质文件数：8。
  - 人员资质记录数：8。
  - 其中无法自动识别的身份证、社保、职称等文件已生成待人工补全占位记录。
- 补齐后端运行环境：
  - `backend/.venv` 缺少 `uvicorn`，已安装 `uvicorn==0.49.0`。
  - 后端已用项目 venv 重启，8000 端口健康接口正常。
- 验证：
  - `test_knowledge_field_normalization.py` 通过。
  - `test_knowledge_bulk_actions.py` 通过。
  - 后端烟雾测试 10/10 通过。
  - API 验证：人员文件 8 个、人员资质记录 8 条。
  - 浏览器验证：前端 5173 可访问，资质页加载正常，控制台 0 错误。

### 2026-06-26：人员资质字段口径调整 ✅

- 将人员资质列表从“证书字段”改为更适合人员材料的字段口径：
  - 资料类型
  - 证件/证书编号
  - 签发/出具日期
  - 有效期/截止日期
  - 出具机构/发证机关
  - 专业/岗位/证明内容
  - 级别/职称/资格
  - 人员姓名
- 后端人员材料占位记录同步调整：
  - 身份证文件名 → `资料类型=身份证明`
  - 社保/养老保险/参保证明 → `资料类型=社保证明`
  - 职称文件 → `资料类型=职称/资格证明`
  - 特种作业/操作证 → `资料类型=特种作业证`
  - 无法判断时 → `资料类型=人员证明材料`
- 占位记录会尽量从文件名推断人员姓名，但遇到地区名、长数字串等明显不像姓名的内容时留空，避免误填。
- 已同步刷新当前数据库中的人员占位记录。
- 验证：
  - 前端测试 38/38 通过。
  - 后端知识库字段测试通过。
  - 后端批量操作测试通过。
  - 后端烟雾测试 10/10 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 后端已重启，健康接口正常。
  - 浏览器烟雾验证：资质页加载正常，控制台 0 错误。

### 2026-06-26：待补全状态与一键分析入口 ✅

- 将占位资质记录从“长期有效”语义改为明确的 `needs_completion` 状态。
- 前端有效期/截止日期列：
  - `needs_completion` 显示“待补全”。
  - 不再把没有有效期的占位记录显示成“长期有效”。
- 资质列表增加“一键分析待补全”入口：
  - 当前分类存在待补全记录时显示提示条。
  - 点击后自动查找这些待补全记录对应的源文件并重新解析。
  - 用户不需要逐条选择文件或逐条点“重新解析”。
- 后端新增待补全源文件识别逻辑：
  - 按 `status='needs_completion'` 或 `scope` 以“待人工补全：”开头识别。
  - 自动过滤正在 pending/parsing 的文件。
  - 支持按当前分类筛选。
- 当前数据库已同步：
  - 人员资质共 8 条。
  - 其中 7 条为待补全，1 条有效。
- 验证：
  - 前端测试 40/40 通过。
  - TypeScript 编译通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 后端知识库批量操作测试通过。
  - 后端字段归一化/占位测试通过。
  - 后端烟雾测试 10/10 通过。
  - 后端已重启，健康接口正常。
  - API 验证人员资质：8 条总数，7 条待补全，1 条有效。
  - 浏览器烟雾验证：资质页加载正常，控制台 0 错误。

### 2026-06-26：人员资质按资料类型细分表格 ✅

- 基于当前已有人员资质文件和记录，归纳出人员资料类型：
  - 身份证明
  - 社保证明
  - 职称/资格证明
  - 特种作业证
  - 其他人员证明
- 资质列表在选择“人员资质”后新增“资料类型”下拉：
  - 默认“全部类型”。
  - 选择具体资料类型后，只展示该类型记录。
  - 表头随资料类型切换。
- 不同资料类型对应不同表头：
  - 身份证明：身份证号、签发日期、有效期、签发机关、身份/角色、人员姓名等。
  - 社保证明：证件号/社保号、出具日期、缴费截止/证明期、参保/缴费情况、缴费期间/月数、人员姓名等。
  - 职称/资格证明：证书编号、取得/签发日期、专业、职称/资格等级、人员姓名等。
  - 特种作业证：证书编号、初领/签发日期、发证机关、作业类别/准操项目、复审/资格级别、人员姓名等。
  - 其他人员证明：编号、出具日期、出具方、证明内容、角色/岗位、人员/主体等。
- “一键分析待补全”也跟随当前筛选：
  - 如果资料类型为“全部类型”，按当前人员资质分类批量分析。
  - 如果选中具体资料类型，只分析当前表格中该类型的待补全源文件。
- 验证：
  - 前端测试 43/43 通过。
  - TypeScript 编译通过。
  - 后端知识库批量操作测试通过。
  - 后端字段归一化/占位测试通过。
  - 后端烟雾测试 10/10 通过。
  - Vite 生产构建通过（仅保留既有 chunk-size 警告）。
  - 浏览器烟雾验证：资质页加载正常，控制台 0 错误。
