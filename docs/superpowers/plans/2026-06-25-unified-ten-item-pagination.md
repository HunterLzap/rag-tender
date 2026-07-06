# Unified Ten-Item Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tender review, uploaded-file, and qualification tables use reusable client-side pagination with 10 rows per page.

**Architecture:** Extract generic pagination helpers into `src/utils/pagination.ts`. Keep independent page state in each page/component and use the same MUI footer pattern for all three tables.

**Tech Stack:** React 18, TypeScript, MUI 5, Node test runner, Vite.

---

### Task 1: Generic pagination helper

**Files:**
- Create: `frontend/src/utils/pagination.ts`
- Create: `frontend/tests/pagination.test.ts`
- Modify: `frontend/src/pages/tenderRequirementView.ts`
- Modify: `frontend/tests/tenderRequirementView.test.ts`

- [ ] Write failing tests for generic 10-row pagination and page clamping.
- [ ] Run tests and confirm missing-module/export failure.
- [ ] Implement `clampPage` and `paginateItems`.
- [ ] Replace tender-specific pagination helpers with imports from the generic module.
- [ ] Run both test files and confirm pass.

### Task 2: Tender review page size

**Files:**
- Modify: `frontend/src/components/RequirementReviewWorkbench.tsx`

- [ ] Change `PAGE_SIZE` from 20 to 10.
- [ ] Verify sequence numbers and range text remain continuous.

### Task 3: Knowledge page pagination

**Files:**
- Modify: `frontend/src/pages/KnowledgePage.tsx`

- [ ] Add independent `filePage` and `qualificationPage` states.
- [ ] Derive paginated file and qualification lists with `paginateItems`.
- [ ] Render only current-page rows.
- [ ] Add matching pagination footers below both tables.
- [ ] Reset qualification page on category change and clamp both pages after reload/delete.

### Task 4: Verification

**Files:**
- Modify: `PROGRESS.md`

- [ ] Run all frontend pure-function tests.
- [ ] Run `npx tsc -b`.
- [ ] Run `npm run build`.
- [ ] Browser-check all three tables.
- [ ] Record results in `PROGRESS.md`.

