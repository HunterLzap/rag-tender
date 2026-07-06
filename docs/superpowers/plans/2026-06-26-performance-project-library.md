# Performance Project Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone performance project library for manual project records linked to uploaded performance files.

**Architecture:** Add a SQLite table plus FastAPI model/schema/service/router for CRUD. Add frontend types/API helpers and a third tab in `KnowledgePage` with a paginated MUI table and CRUD dialog.

**Tech Stack:** FastAPI, SQLite/aiosqlite, Pydantic, React 18, TypeScript, MUI.

---

### Task 1: Backend table and CRUD

- Add `performance_projects` table and migration.
- Add model, schema, service, API router.
- Register router in main app.
- Add script-style backend CRUD test.

### Task 2: Frontend API/types

- Add `PerformanceProject` types.
- Add `frontend/src/api/performance.ts`.
- Add pure form normalization helper and tests.

### Task 3: KnowledgePage tab

- Add `业绩项目` tab.
- Load performance projects and performance-category files.
- Render table with pagination.
- Add create/edit/delete dialogs.

### Task 4: Verification

- Backend CRUD test.
- Backend smoke test.
- Frontend tests.
- TypeScript.
- Vite build.
- Browser smoke.
