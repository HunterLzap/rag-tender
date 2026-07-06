# Review Pagination and Nature Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the review table's internal scrollbar with 20-row pagination and replace pre-match review-state shortcut chips with requirement-nature shortcut chips.

**Architecture:** Keep filtering and pagination client-side because the review page already loads all requirements. Add small pure helpers for nature filtering and page slicing in `tenderRequirementView.ts`, cover them with Node tests, then wire them into the existing MUI workbench without changing backend contracts.

**Tech Stack:** React 18, TypeScript, MUI 5, Node test runner, Vite.

---

### Task 1: Pure pagination and nature-filter helpers

**Files:**
- Modify: `frontend/src/pages/tenderRequirementView.ts`
- Test: `frontend/tests/tenderRequirementView.test.ts`

- [ ] **Step 1: Write failing tests**

Add tests for:

```ts
filterRequirementsByNature(items, 'submission')
paginateRequirements(items, 2, 20)
clampRequirementPage(4, 41, 20)
```

Expected behavior:

- Nature filtering returns only the requested nature.
- Page 2 of 45 items returns IDs 21–40 and reports 3 pages.
- A current page beyond the last valid page is clamped to the last page.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
node --test --experimental-strip-types tests/tenderRequirementView.test.ts
```

Expected: FAIL because the three helper exports do not exist.

- [ ] **Step 3: Implement minimal pure helpers**

Add:

```ts
export const filterRequirementsByNature = (...)
export const clampRequirementPage = (...)
export const paginateRequirements = (...)
```

Use one-based page numbers and return `{ items, page, pageCount, startIndex, endIndex, total }`.

- [ ] **Step 4: Run tests and verify pass**

Run the Node test command again.

Expected: all tests pass.

### Task 2: Wire pagination and nature chips into the workbench

**Files:**
- Modify: `frontend/src/components/RequirementReviewWorkbench.tsx`

- [ ] **Step 1: Add pagination state and derived data**

Add:

```ts
const PAGE_SIZE = 20;
const [page, setPage] = useState(1);
```

Derive nature-filtered results through the new helper, then paginate them. Reset page to 1 when keyword, category, nature, review/match mode, or match filter changes. Clamp the page when filtered data shrinks.

- [ ] **Step 2: Replace pre-match shortcut chips**

Before matching, render:

- 全部
- 能力要求
- 提交资料

Use `natureFilter` as the active value. Keep the existing match-status chips after matching. Remove the duplicate nature `<Select>`.

- [ ] **Step 3: Remove table scrolling**

Change the table container to natural height:

```tsx
<TableContainer>
  <Table size="small">
```

Remove `height`, `overflow`, and `stickyHeader`.

- [ ] **Step 4: Render only current-page rows**

Use `pageItems` in the table body. Compute displayed sequence numbers with `startIndex + index + 1`. Make header select-all operate only on `pageItems`.

- [ ] **Step 5: Add footer pagination**

Render current range, total count, and MUI `<Pagination>` below the table. Keep batch action controls intact.

- [ ] **Step 6: Verify TypeScript**

Run:

```powershell
npx tsc -b
```

Expected: exit code 0.

### Task 3: Full frontend verification and documentation

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run unit tests**

```powershell
node --test --experimental-strip-types tests/tenderRequirementView.test.ts
```

- [ ] **Step 2: Run production build**

```powershell
npm run build
```

- [ ] **Step 3: Update progress**

Record pagination, nature chips, status-column retention, and verification results in `PROGRESS.md`.

- [ ] **Step 4: Browser smoke check**

Verify the real 70-item tender review page:

- no internal table scrollbar;
- 20 rows on page 1;
- nature chips filter correctly;
- review state remains visible in the table;
- page 2 starts at sequence 21.

