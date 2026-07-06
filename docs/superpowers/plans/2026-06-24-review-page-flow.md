# Review Page Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move requirement review to a dedicated route and make qualification matching explicitly user-triggered after review.

**Architecture:** Reuse the existing `RequirementReviewWorkbench` inside a new route-level page. Reduce `TenderPage` to upload/list responsibilities and change `MatchPage` from auto-run behavior to load-existing-results plus explicit start/restart actions.

**Tech Stack:** React 18, React Router 6, TypeScript, MUI 5

---

### Task 1: Dedicated review route

**Files:**
- Create: `frontend/src/pages/TenderReviewPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/RequirementReviewWorkbench.tsx`

- [ ] Add the `/tenders/:id/review` route.
- [ ] Load tender and requirements by URL ID.
- [ ] Add back navigation and unconfirmed-item warning before matching.
- [ ] Navigate to `/match/:id` after submitting the matching task.

### Task 2: Simplify tender list page

**Files:**
- Modify: `frontend/src/pages/TenderPage.tsx`
- Modify: `frontend/src/api/tenders.ts`

- [ ] Remove embedded review state and workbench rendering.
- [ ] Add requirement count/review progress to each completed tender.
- [ ] Add “核对结果” navigation button.

### Task 3: Explicit matching behavior

**Files:**
- Modify: `frontend/src/pages/MatchPage.tsx`

- [ ] Remove matching API call from tender selection effect.
- [ ] Load only existing results on selection.
- [ ] Add explicit start/restart matching button and result refresh polling.
- [ ] Show clear unstarted, matching, completed and failed states.

### Task 4: Verification

**Files:**
- Modify: `PROGRESS.md`

- [ ] Run TypeScript and Vite production build.
- [ ] Browser-test list → review → match navigation.
- [ ] Verify entering `/match/:id` does not call POST `/match/:id`.
- [ ] Update progress documentation.

