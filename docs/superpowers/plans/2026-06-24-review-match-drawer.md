# Review Match Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将核对页改为全宽解析列表、显式知识库匹配、原表展示匹配结果，并通过右侧抽屉按需查看 PDF 原文。

**Architecture:** 核对页负责匹配任务和资质数据加载，工作台组件负责列表展示、筛选、编辑及 PDF 抽屉。纯函数模块负责后端字段归一化、结果关联和异常排序；后端触发接口在提交后台任务前清除旧结果。

**Tech Stack:** React 18、TypeScript、MUI 5、Axios、FastAPI、SQLite、Node test runner、Python unittest

---

### Task 1: 匹配结果视图模型

**Files:**
- Modify: `frontend/src/pages/tenderRequirementView.ts`
- Modify: `frontend/src/api/match.ts`
- Modify: `frontend/src/types/index.ts`
- Test: `frontend/tests/tenderRequirementView.test.ts`

- [ ] 编写失败测试，覆盖 `status` 到 `match_status` 的归一化、异常优先排序和状态筛选。
- [ ] 运行 `node --experimental-strip-types tests/tenderRequirementView.test.ts`，确认测试因缺少新函数失败。
- [ ] 实现最小纯函数和 API 响应归一化。
- [ ] 再次运行测试，确认全部通过。

### Task 2: 清除旧匹配结果

**Files:**
- Modify: `backend/app/services/match_service.py`
- Modify: `backend/app/api/match.py`
- Create: `backend/test_match_trigger.py`

- [ ] 编写失败测试：数据库存在旧结果时，调用清除函数后结果为空。
- [ ] 运行 `python test_match_trigger.py`，确认因缺少函数失败。
- [ ] 实现 `clear_match_results`，并在 POST 接口添加后台任务前调用。
- [ ] 再次运行测试，确认通过。

### Task 3: 核对页匹配编排

**Files:**
- Modify: `frontend/src/pages/TenderReviewPage.tsx`

- [ ] 增加匹配结果、资质列表、匹配错误和轮询状态。
- [ ] 点击匹配后并行准备资质数据，轮询直到结果数覆盖当前要求数。
- [ ] 保持当前路由，不跳转匹配报告页。
- [ ] 解析要求变化时清空过期的匹配结果。

### Task 4: 全宽工作台与 PDF 抽屉

**Files:**
- Modify: `frontend/src/components/RequirementReviewWorkbench.tsx`

- [ ] 删除常驻左右分栏和 iframe。
- [ ] 匹配前显示解析列，匹配后追加资质与匹配状态列。
- [ ] 匹配后切换为匹配状态筛选，并按异常优先排序。
- [ ] 点击页码或“查看原文”打开右侧 Drawer，在抽屉中加载 PDF。
- [ ] 编辑、新增、删除后通知父页面清空过期匹配结果。

### Task 5: 回归与页面验证

**Files:**
- Modify: `PROGRESS.md`

- [ ] 运行前端单元测试。
- [ ] 运行后端匹配、核对和烟雾测试。
- [ ] 运行 `npx tsc -b` 和 `npm run build`。
- [ ] 浏览器确认进入核对页不自动匹配、不显示 PDF，打开原文后出现右侧抽屉。
- [ ] 将实现结果和验证证据追加到 `PROGRESS.md`。
