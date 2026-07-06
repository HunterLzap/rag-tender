# Requirement Review Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a compact master-detail tender requirement review workbench with PDF page navigation, review states, editing, deletion, and batch actions.

**Architecture:** Extend the existing SQLite requirement model with a persisted review status and add focused tender requirement APIs. Replace the accordion frontend with a split table/PDF view while keeping derived sorting and filtering in pure utility functions.

**Tech Stack:** FastAPI, aiosqlite, React 18, TypeScript, MUI 5, browser PDF viewer

---

### Task 1: Backend requirement review capabilities

**Files:**
- Modify: `backend/app/database.py`
- Modify: `backend/app/models/tender.py`
- Modify: `backend/app/schemas/tender.py`
- Modify: `backend/app/services/tender_service.py`
- Modify: `backend/app/api/tenders.py`
- Create: `backend/test_requirement_review.py`

- [ ] Add failing service-level tests for update, delete, batch status update and PDF path resolution.
- [ ] Add `review_status` migration and model fields.
- [ ] Implement update/delete/batch service functions.
- [ ] Add update/delete/batch/PDF endpoints.
- [ ] Run the focused backend test.

### Task 2: Frontend API contract and view utilities

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/tenders.ts`
- Replace: `frontend/src/pages/tenderRequirementView.ts`
- Modify: `frontend/tests/tenderRequirementView.test.ts`

- [ ] Add failing tests for status priority sorting, filters and backend field normalization.
- [ ] Add review status and editable input types.
- [ ] Implement requirement response normalization and new API functions.
- [ ] Implement compact table sorting/filter helpers.
- [ ] Run Node TypeScript regression tests.

### Task 3: Master-detail review workbench

**Files:**
- Create: `frontend/src/components/RequirementReviewWorkbench.tsx`
- Modify: `frontend/src/pages/TenderPage.tsx`
- Delete: `frontend/src/components/TenderRequirementsView.tsx`

- [ ] Build compact toolbar and table with selection.
- [ ] Build PDF pane with page fragment navigation and highlighted raw-text banner.
- [ ] Add keyboard up/down navigation.
- [ ] Add edit dialog, single delete, batch confirmation and batch deletion.
- [ ] Replace the accordion component in `TenderPage`.

### Task 4: Verification and documentation

**Files:**
- Modify: `PROGRESS.md`

- [ ] Run backend focused tests and smoke import.
- [ ] Run frontend regression tests, TypeScript build and Vite build.
- [ ] Restart services and validate the real 96-row tender in a browser.
- [ ] Update project progress.

