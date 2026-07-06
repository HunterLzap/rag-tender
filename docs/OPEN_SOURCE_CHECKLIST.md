# Open Source Release Checklist

Use this before creating the first public GitHub repository.

## Must Do

- [ ] Confirm `.gitignore` excludes `data/`, `backend/output/`, `.env`, `*.db`, logs, `.claude/`, and `.workbuddy/`.
- [ ] Remove real tender files and enterprise qualification files from the repository.
- [ ] Keep only synthetic or fully desensitized samples in `samples/`.
- [ ] Confirm no real API keys exist in tracked files.
- [ ] Configure `RAG_TENDER_SECRET_KEY` locally before running the app.
- [ ] Add screenshots that do not show real company data or API keys.
- [ ] Run backend smoke tests and frontend build.

## Recommended GitHub Description

Local-first RAG tender assistant for tender parsing, qualification matching, rule review, and bid document preparation.

## Suggested Topics

```text
rag
tender
procurement
fastapi
react
sqlite
local-first
document-ai
```

## First Release Boundary

This project is designed for local/self-hosted use. It does not include built-in user accounts or multi-tenant isolation. Teams that need multi-user deployment should add authentication, authorization, and per-user API configuration.
