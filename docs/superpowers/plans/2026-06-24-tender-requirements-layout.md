# Tender Requirements Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat tender requirements table with a summary, filters, collapsible category groups, and expandable requirement rows.

**Architecture:** Keep API contracts unchanged and derive all display state from the existing `TenderRequirement[]`. Add pure utility functions for statistics, filtering, grouping, and validation flags, then compose focused React components inside the existing tender page module.

**Tech Stack:** React 18, TypeScript, MUI 5, Vite

---

### Task 1: Requirement view utilities

**Files:**
- Create: `frontend/src/pages/tenderRequirementView.ts`
- Create: `frontend/src/pages/tenderRequirementView.test.ts`

- [ ] **Step 1: Write failing tests**

Test statistics, keyword/category filtering, hard/numeric filtering, fixed category grouping, and attention detection using representative `TenderRequirement` objects.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd frontend && npx vitest run src/pages/tenderRequirementView.test.ts`

Expected: FAIL because the utility module does not exist.

- [ ] **Step 3: Implement pure utilities**

Export `getRequirementStats`, `filterRequirements`, `groupRequirements`, `hasNumericRequirement`, and `needsAttention`. Use the existing category keys and return stable category ordering.

- [ ] **Step 4: Run utility tests**

Run: `cd frontend && npx vitest run src/pages/tenderRequirementView.test.ts`

Expected: all utility tests pass.

### Task 2: Build the hierarchical requirements view

**Files:**
- Create: `frontend/src/components/TenderRequirementsView.tsx`
- Modify: `frontend/src/pages/TenderPage.tsx`

- [ ] **Step 1: Add display state**

Track selected category, search text, hard-only, numeric-only, expanded categories, and expanded requirement IDs in `TenderRequirementsView`.

- [ ] **Step 2: Add summary and filter controls**

Render four summary cells and a responsive toolbar containing category chips, search, and two switches.

- [ ] **Step 3: Add collapsible category groups**

Render filtered groups in fixed order. Default the qualification group to expanded and display filtered/hard counts in each header.

- [ ] **Step 4: Add expandable requirement rows**

Show title, hard status, numeric condition, page number, two-line summary, attention warning, and expandable full content/raw text.

- [ ] **Step 5: Replace the existing flat table**

Use `TenderRequirementsView` in `TenderPage`. Move the match button into the sticky detail header and preserve parsing, failure, and empty states.

### Task 3: Verify and document

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run TypeScript validation**

Run: `cd frontend && npx tsc -b`

Expected: exit code 0.

- [ ] **Step 2: Run production build**

Run: `cd frontend && npm run build`

Expected: Vite build succeeds.

- [ ] **Step 3: Perform browser smoke check**

Open `http://127.0.0.1:5173/tenders`, select the parsed 148-page tender, and verify summary counts, category collapse, filters, row expansion, and the match button.

- [ ] **Step 4: Update progress**

Append the completed UI change and verification results to `PROGRESS.md`.

