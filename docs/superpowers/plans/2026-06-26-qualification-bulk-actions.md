# Qualification Bulk Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-select, bulk category change, and source-file-level bulk delete to the qualification list.

**Architecture:** Backend adds two service functions and two API endpoints under `/knowledge/qualifications/bulk-*`. Frontend adds API wrappers, selection helpers, checkboxes, a batch toolbar, a category-change dialog, and a destructive delete confirmation dialog.

**Tech Stack:** FastAPI, SQLite/aiosqlite, React 18, TypeScript, MUI, Node test runner.

---

### Task 1: Backend bulk service and API

- Add schema models for bulk requests.
- Add `bulk_update_qualification_category()`.
- Add `bulk_delete_qualifications_by_source()`.
- Add API routes.
- Verify with focused backend tests.

### Task 2: Frontend API and selection helpers

- Add API wrappers.
- Add pure selection helpers and tests.

### Task 3: KnowledgePage UI

- Add row checkboxes and current-page select all.
- Add selected count toolbar.
- Add bulk category dialog and source-delete confirmation dialog.
- Refresh files and qualifications after operations.

### Task 4: Verification

- Run backend tests.
- Run frontend tests.
- Run TypeScript.
- Run Vite build.
- Browser-smoke `/knowledge`.
